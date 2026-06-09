"""
OpenSMILE Bridge ↔ Persona Engine Integration
Connects voice feature extraction directly to persona profiling
"""

import json
import time
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

from .extractor import OpenSmileExtractor
from .midi_mapper import MidiMapper
from .i2i_integration import I2IManager
from .config import SAMPLE_RATE, I2I_VESSEL_DIR, I2I_SPEAKER_ID


class PersonaIntegrationBridge:
    """
    Bridge between OpenSMILE voice features and persona engine profiling.
    
    When a voice is detected and features extracted, this bridge:
    1. Captures cadence (pause patterns, speaking rate)
    2. Captures prosody (pitch contour, energy envelope)
    3. Packages into persona-compatible format
    4. Publishes to I2I for persona engine consumption
    """

    def __init__(self, vessel_dir: str = I2I_VESSEL_DIR, speaker_id: str = I2I_SPEAKER_ID):
        self.extractor = OpenSmileExtractor()
        self.midi_mapper = MidiMapper()
        self.i2i = I2IManager(vessel_dir=vessel_dir, speaker_id=f"{speaker_id}-persona")

        # Cadence tracking
        self._pause_start: Optional[float] = None
        self._speech_start: Optional[float] = None
        self._pause_durations: list = []
        self._speech_durations: list = []
        self._frame_timestamps: list = []
        self._f0_track: list = []
        self._energy_track: list = []

        # Thresholds
        self._voicing_threshold = 0.5
        self._pause_min_ms = 150
        self._is_speaking = False

        print(f"🔗 PersonaIntegrationBridge initialized → {vessel_dir}")

    def feed_audio(self, audio_chunk: np.ndarray) -> None:
        """Feed audio and track persona-relevant features"""
        self.extractor.feed_audio(audio_chunk)
        features = self.extractor.extract()

        if features:
            self._track_cadence(features)
            self._track_prosody(features)

    def _track_cadence(self, features: Dict[str, Any]) -> None:
        """Track speaking cadence from voicing probability"""
        now = time.time()
        voicing = features.get("voicing_probability", 0.0)

        if voicing > self._voicing_threshold:
            if not self._is_speaking:
                if self._pause_start is not None:
                    pause_ms = (now - self._pause_start) * 1000
                    if pause_ms > self._pause_min_ms:
                        self._pause_durations.append(pause_ms)
                self._speech_start = now
                self._is_speaking = True
        else:
            if self._is_speaking:
                if self._speech_start is not None:
                    self._speech_durations.append((now - self._speech_start) * 1000)
                self._pause_start = now
                self._is_speaking = False

        self._frame_timestamps.append(now)

    def _track_prosody(self, features: Dict[str, Any]) -> None:
        """Track prosodic features"""
        if "f0_hz" in features and features["f0_hz"] > 0:
            self._f0_track.append(features["f0_hz"])
        if "loudness" in features:
            self._energy_track.append(features["loudness"])

    def get_persona_manifest(self) -> Dict[str, Any]:
        """Build a persona-compatible manifest from tracked features"""
        import numpy as np

        f0_arr = np.array(self._f0_track) if self._f0_track else np.array([120.0])
        energy_arr = np.array(self._energy_track) if self._energy_track else np.array([0.0])
        pauses = self._pause_durations if self._pause_durations else [0.0]
        speech = self._speech_durations if self._speech_durations else [0.0]

        # Cadence
        mean_pause = float(np.mean(pauses)) / 1000.0
        mean_speech = float(np.mean(speech)) / 1000.0 if speech else 1.0
        wpm_estimate = 60.0 / max(mean_speech, 0.1) if mean_speech > 0 else 150.0

        # Prosody
        mean_f0 = float(np.mean(f0_arr))
        f0_std = float(np.std(f0_arr))
        mean_energy = float(np.mean(energy_arr))

        manifest = {
            "cadence": {
                "mean_wpm": wpm_estimate,
                "wpm_std": wpm_estimate * 0.2,
                "mean_pause_duration": mean_pause,
                "pause_duration_std": float(np.std(pauses)) / 1000.0,
                "thought_duration_mean": mean_speech,
                "thought_duration_std": float(np.std(speech)) / 1000.0,
            },
            "prosody": {
                "mean_f0": mean_f0,
                "f0_std": f0_std,
                "f0_range": [float(np.min(f0_arr)), float(np.max(f0_arr))],
                "mean_energy": mean_energy,
                "energy_std": float(np.std(energy_arr)),
            },
            "groove": {
                "conversational_bpm": 60.0 / max(mean_speech + mean_pause, 0.5),
                "turn_style": "rhythmic" if mean_pause > 0.3 else "patient",
            },
            "frame_count": len(self._frame_timestamps),
            "duration_seconds": self._frame_timestamps[-1] - self._frame_timestamps[0] 
                if len(self._frame_timestamps) > 1 else 0.0,
        }

        return manifest

    def publish_persona_bottle(self) -> bool:
        """Publish a persona manifest bottle to the fleet"""
        manifest = self.get_persona_manifest()
        bottle = self.i2i.create_bottle(
            bottle_type="PERSONA_MANIFEST",
            payload={
                "type": "PERSONA_MANIFEST",
                "manifest": manifest,
                "speaker_id": f"{I2I_SPEAKER_ID}-profile",
                "timestamp": time.time(),
                "features": {
                    "pause_count": len(self._pause_durations),
                    "speech_segments": len(self._speech_durations),
                    "f0_samples": len(self._f0_track),
                },
            },
            context={
                "source": "opensmile-bridge",
                "module": "persona_integration",
            }
        )
        return self.i2i.publish_bottle(bottle)

    def reset(self) -> None:
        """Reset all tracking"""
        self._pause_durations.clear()
        self._speech_durations.clear()
        self._frame_timestamps.clear()
        self._f0_track.clear()
        self._energy_track.clear()
        self._is_speaking = False
        self._pause_start = None
        self._speech_start = None
        self.extractor.clear()
