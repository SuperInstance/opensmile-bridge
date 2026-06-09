#!/usr/bin/env python3
"""
OpenSMILE Bridge Configuration

Centralized config for the modular opensmile bridge system.
"""

import os
from typing import Optional

# Environment variables prefix: OPENSMILE_BRIDGE_

# Core configuration
PORT: int = int(os.environ.get("OPENSMILE_BRIDGE_PORT", "8765"))
SAMPLE_RATE: int = int(os.environ.get("OPENSMILE_BRIDGE_SAMPLE_RATE", "16000"))
FRAME_SIZE: int = int(os.environ.get("OPENSMILE_BRIDGE_FRAME_SIZE", "1024"))
HOP_SIZE: int = int(os.environ.get("OPENSMILE_BRIDGE_HOP_SIZE", "512"))
CHUNK_MS: float = float(HOP_SIZE / SAMPLE_RATE * 1000)

# OpenSMILE Configuration
FEATURE_SET: str = os.environ.get("OPENSMILE_FEATURE_SET", "eGeMAPSv02")
FEATURE_LEVEL: str = os.environ.get("OPENSMILE_FEATURE_LEVEL", "LowLevelDescriptors")
STREAMING_FEATURE_LIMIT: Optional[int] = int(os.environ.get("OPENSMILE_STREAMING_LIMIT", "25")) if os.environ.get("OPENSMILE_STREAMING_LIMIT") else None

# Fleet Integration
I2I_ENABLED: bool = os.environ.get("OPENSMILE_BRIDGE_I2I_ENABLED", "false").lower() == "true"
I2I_VESSEL_DIR: str = os.environ.get("OPENSMILE_BRIDGE_VESSEL_DIR", "/tmp/i2i-vessel")
I2I_SPEAKER_ID: str = os.environ.get("OPENSMILE_BRIDGE_SPEAKER_ID", "opensmile-bridge")

# Bridge endpoints
GHOST_BRIDGE_URL: str = os.environ.get("GHOST_BRIDGE_URL", "ws://localhost:8767")
TMINUS_DISPATCHER_URL: str = os.environ.get("TMINUS_DISPATCHER_URL", "ws://localhost:8768")

# MIDI Configuration
MIDI_MIN: int = int(os.environ.get("OPENSMILE_BRIDGE_MIDI_MIN", "0"))
MIDI_MAX: int = int(os.environ.get("OPENSMILE_BRIDGE_MIDI_MAX", "127"))

# Logging
LOG_LEVEL: str = os.environ.get("OPENSMILE_BRIDGE_LOG_LEVEL", "INFO")

# Feature mapping dictionary
FEATURE_MAPPING: dict[str, str] = {
    'F0semitoneFrom27.5Hz_sma3nz': 'f0_semitones',
    'F0raw_sma3nz': 'f0_raw',
    'Loudness_sma3': 'loudness',
    'jitterLocal_sma3nz': 'jitter',
    'shimmerLocaldB_sma3nz': 'shimmer',
    'HNR_sma3nz': 'hnr',
    'alphaRatio_sma3': 'alpha_ratio',
    'hammarbergIndex_sma3': 'hammarberg_index',
    'slope0-500Hz_sma3': 'slope_0_500',
    'slope500-1500Hz_sma3': 'slope_500_1500',
    'spectralFlux_sma3': 'spectral_flux',
    'mfcc1_sma3': 'mfcc1',
    'mfcc2_sma3': 'mfcc2',
    'mfcc3_sma3': 'mfcc3',
    'mfcc4_sma3': 'mfcc4',
    'mfcc5_sma3': 'mfcc5',
    'mfcc6_sma3': 'mfcc6',
    'mfcc7_sma3': 'mfcc7',
    'mfcc8_sma3': 'mfcc8',
    'mfcc9_sma3': 'mfcc9',
    'mfcc10_sma3': 'mfcc10',
    'mfcc11_sma3': 'mfcc11',
    'mfcc12_sma3': 'mfcc12',
    'voicingFinalUnclipped_sma3': 'voicing_probability',
}

# MIDI CC Mapping for features
MIDI_CC_MAPPING: dict[str, int] = {
    'f0_semitones': 1,      # Pitch → CC1 (Pitch Bend is separate, but semitones here)
    'loudness': 7,            # Loudness → CC7 (Volume)
    'jitter': 16,             # Vocal roughness → CC16 (Distortion)
    'shimmer': 17,            # Amplitude instability → CC17 (Tremolo)
    'hnr': 2,               # Breathiness → CC2 (Breath Control)
    'alpha_ratio': 74,       # Vowel openness → CC74 (Cutoff)
    'spectral_flux': 75,      # Brightness → CC75
    'mfcc1': 12,            # MFCC timbre → CC12
    'mfcc2': 13,            # MFCC timbre → CC13
    'mfcc3': 14,            # MFCC timbre → CC14
    'mfcc4': 15,            # MFCC timbre → CC15
    'mfcc5': 16,            # MFCC timbre → CC16
    'mfcc6': 17,            # MFCC timbre → CC17
    'mfcc7': 18,            # MFCC timbre → CC18
    'mfcc8': 19,            # MFCC timbre → CC19
    'mfcc9': 20,            # MFCC timbre → CC20
    'mfcc10': 21,           # MFCC timbre → CC21
    'mfcc11': 22,           # MFCC timbre → CC22
    'mfcc12': 23,           # MFCC timbre → CC23
    'voicing_probability': 70, # Voicing → CC70 (Expression)
}


def validate_config() -> bool:
    """Validate configuration values."""
    valid = True
    if PORT < 1 or PORT > 65535:
        print(f"ERROR: Invalid port {PORT}")
        valid = False
    if SAMPLE_RATE not in [8000, 16000, 22050, 44100]:
        print(f"WARNING: Uncommon sample rate {SAMPLE_RATE}")
    return valid


def get_feature_config_str() -> str:
    """Return a string describing the feature set and count."""
    from opensmile import FeatureSet, FeatureLevel
    try:
        fs = getattr(FeatureSet, FEATURE_SET)
        fl = getattr(FeatureLevel, FEATURE_LEVEL)
        count = FeatureSet.num_features(fs, fl)
        return f"{FEATURE_SET}::{FEATURE_LEVEL} ({count} features)"
    except Exception:
        return f"{FEATURE_SET}::{FEATURE_LEVEL} (unknown count)"
