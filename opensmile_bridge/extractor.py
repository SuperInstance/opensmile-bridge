#!/usr/bin/env python3
"""
OpenSMILE Feature Extraction - Modular implementation
Supports both streaming and batch feature extraction
"""

import os
import queue
import numpy as np
from typing import Callable, Optional, Dict, Any
from collections import deque

# Try to import opensmile
opensmile_available = False
try:
    import opensmile
    opensmile_available = True
except ImportError:
    print("WARNING: opensmile not available. Install with pip install opensmile")

from .config import FEATURE_MAPPING, SAMPLE_RATE, FRAME_SIZE, HOP_SIZE


class StreamingOpenSmile:
    """
    Modular streaming OpenSMILE feature extractor
    Uses background ring buffer processing for real-time audio streams
    """

    def __init__(
        self,
        config_path: str,
        feature_level: str = "lld",
        callback: Optional[Callable[[Dict[str, Any], int], None]] = None,
        sample_rate: int = 16000,
        chunk_ms: float = 32.0,
    ):
        """
        Initialize streaming OpenSMILE extractor
        
        Args:
            config_path: Path to OpenSMILE config file
            feature_level: Feature level to extract (lld, functionals, etc.)
            callback: Callback function for processed feature frames
            sample_rate: Audio sample rate
            chunk_ms: Chunk size in milliseconds per frame
        """
        if not opensmile_available:
            raise ImportError("opensmile package is required for StreamingOpenSmile")

        self.config_path = config_path
        self.feature_level = feature_level
        self.callback = callback
        self.sample_rate = sample_rate
        self.chunk_samples = int(chunk_ms * sample_rate / 1000)
        self.audio_buffer = deque(maxlen=8192 * 10)  # 10s buffer

        # Initialize OpenSMILE
        self.smile = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
        )

        # Import required for streaming
        try:
            from opensmile import StreamingExtractor
            self.streamer = StreamingExtractor(
                config_path, sample_rate, feature_level
            )
            self._streaming_ready = True
        except Exception as e:
            print(f"WARNING: Streaming mode not available: {e}")
            self._streaming_ready = False

        self.frame_count = 0
        self.running = False

    def start(self) -> None:
        """Start the streaming extractor thread"""
        self.running = True
        if self._streaming_ready:
            self.streamer.start()

    def write(self, audio_chunk: np.ndarray) -> None:
        """Write audio chunk to the stream"""
        if not self.running:
            return

        if self._streaming_ready:
            self.streamer.write(audio_chunk.tobytes())
            # Process available frames
            while self.streamer.has_frame():
                frame = self.streamer.read_frame()
                if self.callback:
                    self.callback(frame, self.frame_count)
                self.frame_count += 1
        else:
            # Fallback batch mode
            self.audio_buffer.extend(audio_chunk.tolist())
            if len(self.audio_buffer) >= self.chunk_samples:
                self._process_batch_frame()

    def _process_batch_frame(self) -> None:
        """Process a single batch frame from buffer"""
        frame_data = np.array(list(self.audio_buffer)[:self.chunk_samples], dtype=np.float32)
        result = self.smile.process_signal(frame_data, self.sample_rate)
        if self.callback:
            self.callback(result.to_dict(), self.frame_count)
        self.frame_count +=1
        # Clear the processed data
        for _ in range(self.chunk_samples):
            self.audio_buffer.popleft()

    def stop(self) -> None:
        """Stop the streaming extractor"""
        self.running = False
        if self._streaming_ready:
            self.streamer.stop()


class OpenSmileExtractor:
    """
    Unified OpenSMILE extractor that supports both streaming and batch modes
    """

    def __init__(
        self,
        use_streaming: bool = True,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Initialize OpenSMILE extractor
        
        Args:
            use_streaming: Enable streaming mode for real-time audio
            callback: Callback for processed feature frames
        """
        self._streaming = None
        self._batch_smile = None
        self._feature_queue = queue.Queue(maxsize=100)
        self.last_features: Optional[Dict[str, Any]] = None
        self.frame_count = 0

        # Create callback wrapper that stores and forwards features
        def _internal_callback(feats: Dict[str, Any], ts: int):
            parsed_feats = self._parse_features(feats)
            self.last_features = parsed_feats
            self._feature_queue.put(parsed_feats)
            if callback:
                callback(parsed_feats)

        if use_streaming and opensmile_available:
            try:
                # Use default eGeMAPS config
                config_path = os.path.join(
                    os.path.dirname(opensmile.__file__),
                    "config",
                    "egemaps",
                    "v02",
                    "eGeMAPSv02.conf"
                )
                self._streaming = StreamingOpenSmile(
                    config_path=config_path,
                    callback=_internal_callback
                )
                self._streaming.start()
                print(f"✅ Streaming OpenSMILE initialized: 25 eGeMAPS features")
            except Exception as e:
                print(f"⚠️  Failed to initialize streaming OpenSMILE: {e}")
                self._streaming = None

        # Fallback to batch mode
        if not self._streaming and opensmile_available:
            self._batch_smile = opensmile.Smile(
                feature_set=opensmile.FeatureSet.eGeMAPSv02,
                feature_level=opensmile.FeatureLevel.LowLevelDescriptors,
            )
            self._batch_buffer = deque(maxlen=8192)
            print(f"✅ Batch-mode OpenSMILE initialized: 25 eGeMAPS features")

    def feed_audio(self, audio_chunk: np.ndarray) -> None:
        """Feed audio chunk for feature extraction"""
        if self._streaming is not None:
            self._streaming.write(audio_chunk)
        elif self._batch_smile is not None:
            self._batch_buffer.extend(audio_chunk.tolist())
            if len(self._batch_buffer) >= FRAME_SIZE:
                self._process_batch_frame()

    def _process_batch_frame(self) -> None:
        """Process a single batch frame"""
        if not self._batch_smile:
            return

        frame = np.array(list(self._batch_buffer)[:FRAME_SIZE], dtype=np.float32)
        try:
            result = self._batch_smile.process_signal(frame, SAMPLE_RATE)
            parsed = self._parse_features(result.to_dict())
            self.last_features = parsed
            self.frame_count +=1
        except Exception as e:
            print(f"⚠️  OpenSMILE processing error: {e}")

    def extract(self) -> Optional[Dict[str, Any]]:
        """Get next available feature frame"""
        try:
            return self._feature_queue.get_nowait()
        except queue.Empty:
            return None

    def _parse_features(self, raw_features: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw OpenSMILE features into our standardized dictionary"""
        parsed = {}

        # Apply feature mapping
        for raw_key, friendly_key in FEATURE_MAPPING.items():
            if raw_key in raw_features:
                value = raw_features[raw_key]
                if isinstance(value, np.ndarray):
                    # Take the first value if array (for functionals)
                    value = value[0] if len(value) > 0 else 0.0
                elif isinstance(value, dict):
                    # Some OpenSMILE outputs are nested dicts (functionals)
                    # Try to extract a scalar, skip if not possible
                    vals = [v for v in value.values() if isinstance(v, (int, float, np.floating)) and not np.isnan(v)]
                    value = float(np.mean(vals)) if vals else 0.0
                elif isinstance(value, (int, float, np.floating)):
                    pass  # fine as-is
                elif value is None or (isinstance(value, float) and np.isnan(value)):
                    value = 0.0
                else:
                    try:
                        value = float(value)
                    except (TypeError, ValueError):
                        value = 0.0
                parsed[friendly_key] = float(value)

        # Derive additional useful features
        if "loudness" in parsed:
            # Normalize loudness to 0-1 range
            parsed["normalized_loudness"] = np.clip(parsed["loudness"] / 100.0, 0.0, 1.0)

        if "f0_semitones" in parsed:
            # Convert semitones to Hz
            parsed["f0_hz"] = 27.5 * (2 ** (parsed["f0_semitones"] / 12.0))

        return parsed

    def clear(self) -> None:
        """Clear any pending features and buffers"""
        while not self._feature_queue.empty():
            try:
                self._feature_queue.get_nowait()
            except queue.Empty:
                break
        if hasattr(self, "_batch_buffer"):
            self._batch_buffer.clear()
        self.last_features = None

    def get_feature_count(self) -> int:
        """Return number of extracted features"""
        return len(self.last_features.keys()) if self.last_features else 0


def test_extractor():
    """Test the extractor with test audio"""
    print("🏃 Running OpenSMILE extractor test...")
    extractor = OpenSmileExtractor()

    # Generate test sine wave
    duration_s = 1.0
    freq_hz = 440.0
    samples = int(SAMPLE_RATE * duration_s)
    t = np.linspace(0, duration_s, samples, endpoint=False)
    audio = np.sin(2 * np.pi * freq_hz * t)

    # Feed audio
    extractor.feed_audio(audio)

    # Get features
    features = extractor.extract()
    if features:
        print(f"✅ Extracted {len(features)} features:")
        for key, value in list(features.items())[:5]:
            print(f"  {key}: {value:.4f}")
    else:
        print("❌ No features extracted")

    extractor.clear()


if __name__ == "__main__":
    test_extractor()
