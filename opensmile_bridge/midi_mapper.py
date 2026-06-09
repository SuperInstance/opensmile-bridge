#!/usr/bin/env python3
"""
OpenSMILE → MIDI CC Mapper

Converts standardized voice features from OpenSMILE extractor to MIDI CC messages
ready for use by synthesizers and bridge clients.
"""

import numpy as np
from typing import Dict, Any, Optional, Tuple

from .config import MIDI_CC_MAPPING, MIDI_MIN, MIDI_MAX


class MidiMapper:
    """
    Map voice features to MIDI CC messages
    """

    def __init__(
        self,
        custom_mapping: Optional[Dict[str, int]] = None,
        midi_min: int = MIDI_MIN,
        midi_max: int = MIDI_MAX,
    ):
        """
        Initialize MIDI CC mapper
        
        Args:
            custom_mapping: Optional custom feature→CC# mapping
            midi_min: Minimum MIDI CC value (0-127)
            midi_max: Maximum MIDI CC value (0-127)
        """
        self._midi_min = midi_min
        self._midi_max = midi_max
        self._cc_mapping: Dict[str, int] = {**MIDI_CC_MAPPING, **(custom_mapping or {})}
        self._normalization_cache: Dict[str, Tuple[float, float]] = {}

    def map_feature_to_cc(self, feature_name: str, value: float) -> Optional[Tuple[int, int]]:
        """
        Map a single feature to a MIDI CC message
        
        Args:
            feature_name: Name of feature to map
            value: Raw feature value
            
        Returns:
            Tuple of (cc_number, cc_value) or None if no mapping
        """
        cc_number = self._cc_mapping.get(feature_name)
        if cc_number is None:
            return None

        normalized = self._normalize_value(feature_name, value)
        cc_value = int(self._midi_min + normalized * (self._midi_max - self._midi_min))
        return (cc_number, cc_value)

    def map_all_features(self, features: Dict[str, Any]) -> Dict[int, int]:
        """
        Map all available features to MIDI CC messages
        
        Args:
            features: Dictionary of standardized voice features
            
        Returns:
            Dictionary of {cc_number: cc_value}
        """
        cc_messages = {}
        
        for feature_name, value in features.items():
            cc_info = self.map_feature_to_cc(feature_name, value)
            if cc_info:
                cc_number, cc_value = cc_info
                cc_messages[cc_number] = cc_value

        return cc_messages

    def get_midi_note_from_f0(self, f0_hz: float, middle_a: float = 440.0) -> int:
        """
        Convert fundamental frequency to MIDI note number
        
        Args:
            f0_hz: Fundamental frequency in Hz
            middle_a: Frequency of middle A (default 440.0)
            
        Returns:
            MIDI note number (0-127)
        """
        if f0_hz <= 0:
            return 0
        
        # MIDI note formula: note = 69 + 12 * log2(f0 / 440)
        midi_note = 69 + 12 * np.log2(f0_hz / middle_a)
        return int(np.clip(midi_note, 0, 127))

    def get_pitch_bend_from_f0(self, f0_hz: float, center: float = 0.0) -> int:
        """
        Convert fundamental frequency to MIDI pitch bend value
        
        Args:
            f0_hz: Fundamental frequency in Hz
            center: Center frequency (default 0.0, will use configured center)
            
        Returns:
            MIDI pitch bend value (0-16383, 8192 is center)
        """
        if f0_hz <= 0:
            return 8192
            
        # Convert to semitones from center
        if center > 0:
            semitones = 12 * np.log2(f0_hz / center)
        else:
            # Use A440 as default center
            semitones = 12 * np.log2(f0_hz / 440.0)
            
        # Convert to pitch bend units (8192 = 0 bend, ±8192 full range)
        bend_range = 8192  # 1 semitone bend range
        bend = int(8192 + semitones * bend_range * 12)
        return int(np.clip(bend, 0, 16383))

    def add_normalization_range(self, feature_name: str, min_val: float, max_val: float) -> None:
        """
        Add manual normalization range for a feature
        
        Args:
            feature_name: Name of feature
            min_val: Minimum expected value
            max_val: Maximum expected value
        """
        self._normalization_cache[feature_name] = (min_val, max_val)

    def _normalize_value(self, feature_name: str, value: float) -> float:
        """
        Normalize a feature value to 0-1 range
        Uses cached ranges if available, otherwise uses global min/max
        
        Args:
            feature_name: Name of feature
            value: Raw feature value
            
        Returns:
            Normalized value 0.0-1.0
        """
        # Check for cached normalization range
        if feature_name in self._normalization_cache:
            min_val, max_val = self._normalization_cache[feature_name]
            if max_val > min_val:
                return np.clip((value - min_val) / (max_val - min_val), 0.0, 1.0)

        # Special case mapping for known features
        match feature_name:
            case "loudness" | "normalized_loudness":
                # Loudness typically ranges -60 to 0 dB
                return np.clip((value + 60) / 60.0, 0.0, 1.0)
                
            case "f0_semitones" | "f0_hz":
                # Human voice range: ~80Hz (low male) to 1100Hz (soprano)
                return np.clip((value - 80) / (1100 - 80), 0.0, 1.0)
                
            case "jitter":
                # Jitter typically <0.05
                return np.clip(value / 0.05, 0.0, 1.0)
                
            case "shimmer":
                # Shimmer typically <0.05dB
                return np.clip(value / 0.05, 0.0, 1.0)
                
            case "hnr":
                # HNR typically 0-40dB
                return np.clip(value / 40.0, 0.0, 1.0)
                
            case "voicing_probability":
                # Already 0-1 range
                return np.clip(value, 0.0, 1.0)
                
            case _:
                # Default to min-max of available values
                return np.clip(value, 0.0, 1.0)


# Pre-configured standard mappers
STANDARD_MAPPER = MidiMapper()
JAZZ_MAPPER = MidiMapper({
    "f0_semitones": 11,   # Pitch bend
    "loudness": 7,        # Volume
    "jitter": 16,         # Distortion
    "shimmer": 17,        # Tremolo
    "hnr": 2,             # Breath control
})

FLEET_MIDI_MAPPING = {
    "cc": MIDI_CC_MAPPING,
    "note_basis": 60,     # Middle C
    "pitch_channel": 1,   # MIDI channel 1 for pitch bend
    "cc_channel": 2,      # MIDI channel 2 for CC messages
}


def test_mapper():
    """Test the MIDI mapper"""
    print("🏃 Running MIDI mapper test...")
    mapper = MidiMapper()
    
    # Test feature mapping
    test_features = {
        "f0_hz": 440.0,
        "loudness": -20.0,
        "jitter": 0.01,
        "shimmer": 0.005,
        "hnr": 20.0,
        "voicing_probability": 0.9,
    }
    
    print("\n✅ Feature → CC Mapping:")
    for feature, value in test_features.items():
        cc = mapper.map_feature_to_cc(feature, value)
        if cc:
            cc_num, cc_val = cc
            print(f"  {feature:25} {value:>8.4f} → CC{cc_num:3}: {cc_val:3}")
    
    # Test pitch bend
    print("\n✅ MIDI Note/Pitch Bend:")
    for f0_hz in [220, 440, 880]:
        note = mapper.get_midi_note_from_f0(f0_hz)
        bend = mapper.get_pitch_bend_from_f0(f0_hz)
        print(f"  {f0_hz:>5}Hz → MIDI Note {note:3}, Bend {bend:5}")


if __name__ == "__main__":
    test_mapper()
