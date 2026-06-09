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

# Vessel agent configuration
HEARTBEAT_INTERVAL: int = int(os.environ.get("OPENSMILE_BRIDGE_HEARTBEAT", "30"))
PERSONA_TRACKING: bool = os.environ.get("OPENSMILE_BRIDGE_PERSONA", "false").lower() == "true"
MIDI_ENABLED: bool = os.environ.get("OPENSMILE_BRIDGE_MIDI", "true").lower() == "true"

# Feature mapping dictionary
# Maps actual OpenSMILE eGeMAPSv02 LLD column names to friendly keys
# Verified against opensmile 2.6.6 — all 25 columns mapped
FEATURE_MAPPING: dict[str, str] = {
    'Loudness_sma3': 'loudness',
    'alphaRatio_sma3': 'alpha_ratio',
    'hammarbergIndex_sma3': 'hammarberg_index',
    'slope0-500_sma3': 'slope_0_500',
    'slope500-1500_sma3': 'slope_500_1500',
    'spectralFlux_sma3': 'spectral_flux',
    'mfcc1_sma3': 'mfcc1',
    'mfcc2_sma3': 'mfcc2',
    'mfcc3_sma3': 'mfcc3',
    'mfcc4_sma3': 'mfcc4',
    'F0semitoneFrom27.5Hz_sma3nz': 'f0_semitones',
    'jitterLocal_sma3nz': 'jitter',
    'shimmerLocaldB_sma3nz': 'shimmer',
    'HNRdBACF_sma3nz': 'hnr',
    'logRelF0-H1-H2_sma3nz': 'log_rel_f0_h1_h2',
    'logRelF0-H1-A3_sma3nz': 'log_rel_f0_h1_a3',
    'F1frequency_sma3nz': 'f1_freq',
    'F1bandwidth_sma3nz': 'f1_bw',
    'F1amplitudeLogRelF0_sma3nz': 'f1_amplitude',
    'F2frequency_sma3nz': 'f2_freq',
    'F2bandwidth_sma3nz': 'f2_bw',
    'F2amplitudeLogRelF0_sma3nz': 'f2_amplitude',
    'F3frequency_sma3nz': 'f3_freq',
    'F3bandwidth_sma3nz': 'f3_bw',
    'F3amplitudeLogRelF0_sma3nz': 'f3_amplitude',
}

# MIDI CC Mapping for features
MIDI_CC_MAPPING: dict[str, int] = {
    'f0_semitones': 1,      # Pitch → CC1 (Pitch Bend is separate, semitones here)
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
    'log_rel_f0_h1_h2': 70,   # Voicing quality → CC70 (Expression)
    'log_rel_f0_h1_a3': 71,   # Spectral tilt → CC71 (Timbre)
    'f1_freq': 74,            # First formant → CC74 (Cutoff)
    'f1_bw': 75,              # F1 bandwidth → CC75
    'f2_freq': 76,            # Second formant → CC76
    'f2_bw': 77,              # F2 bandwidth → CC77
    'f3_freq': 78,            # Third formant → CC78
    'f3_bw': 79,              # F3 bandwidth → CC79
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
