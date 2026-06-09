#!/usr/bin/env python3
"""
Full pipeline integration test for OpenSMILE Bridge
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opensmile_bridge.extractor import OpenSmileExtractor
from opensmile_bridge.midi_mapper import MidiMapper, STANDARD_MAPPER
from opensmile_bridge.i2i_integration import I2IManager
from opensmile_bridge.persona_integration import PersonaIntegrationBridge
from opensmile_bridge.config import SAMPLE_RATE, FEATURE_MAPPING


def test_extractor():
    """Test the OpenSMILE extractor with synthetic audio"""
    print("🧪 Testing OpenSMILE extractor...")
    extractor = OpenSmileExtractor(use_streaming=False)

    # Generate test sine wave
    duration = 2.0
    freq = 440.0
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    audio = np.sin(2 * np.pi * freq * t).astype(np.float32)

    # Process in chunks
    chunk_size = 512
    for i in range(0, len(audio), chunk_size):
        chunk = audio[i:i + chunk_size]
        extractor.feed_audio(chunk)

    features = extractor.extract()
    if features:
        print(f"  ✅ Extracted {len(features)} features after feed")
        for key, val in list(features.items())[:4]:
            print(f"     {key}: {val:.4f}")
    else:
        print("  ⚠️  No features extracted yet (need more audio)")
    
    extractor.clear()
    return True


def test_midi_mapping():
    """Test MIDI mapping with sample features"""
    print("🧪 Testing MIDI mapper...")
    mapper = MidiMapper()

    # Sample test data
    test_features = {
        "f0_hz": 440.0,
        "loudness": -20.0,
        "jitter": 0.01,
        "shimmer": 0.005,
        "hnr": 20.0,
        "voicing_probability": 0.9,
    }

    cc_messages = mapper.map_all_features(test_features)
    print(f"  ✅ Mapped to {len(cc_messages)} CC messages:")
    for cc_num, cc_val in sorted(cc_messages.items())[:5]:
        print(f"     CC{cc_num} → {cc_val}")

    # Test note mapping
    midi_note = mapper.get_midi_note_from_f0(440.0)
    assert midi_note == 69, f"Expected MIDI note 69 (A4), got {midi_note}"
    print(f"  ✅ MIDI note mapping: 440Hz → note {midi_note} (A4)")

    return True


def test_i2i_bottles():
    """Test I2I bottle publishing"""
    print("🧪 Testing I2I integration...")
    test_dir = Path(tempfile.mkdtemp(prefix="test-i2i-"))
    manager = I2IManager(vessel_dir=str(test_dir), speaker_id="test-speaker")

    # Publish test features
    test_features = {
        "frame": 1,
        "timestamp": 0.0,
        "raw_features": {
            "f0_hz": 440.0,
            "loudness": -20.0,
        },
        "midi_cc": {7: 80, 1: 60}
    }

    success = manager.publish_features(test_features)
    assert success, "Failed to publish features"

    # Verify bottle was written
    bottle_files = list((test_dir / "outgoing").glob("*.json"))
    assert len(bottle_files) > 0, "No bottle files created"
    bottle = json.loads(bottle_files[0].read_text())
    assert bottle["bottle"]["type"] == "FEATURES"
    print(f"  ✅ Published and verified bottle: {bottle_files[0].name}")

    # Cleanup
    shutil.rmtree(test_dir)
    return True


def test_persona_integration():
    """Test persona engine integration"""
    print("🧪 Testing persona engine integration...")
    test_dir = Path(tempfile.mkdtemp(prefix="test-persona-"))
    bridge = PersonaIntegrationBridge(vessel_dir=str(test_dir), speaker_id="test-persona")

    # Feed synthetic voicing patterns
    sample_rate = 16000
    duration = 3.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # Simulate speech: oscillate between voiced and unvoiced
    voiced = np.sin(2 * np.pi * 200 * t)
    voiced[voiced > 0] *= 0.8
    voiced[voiced <= 0] *= -0.2
    
    bridge.feed_audio(voiced.astype(np.float32))
    
    # Get manifest
    manifest = bridge.get_persona_manifest()
    assert "cadence" in manifest, "Missing cadence in manifest"
    assert "prosody" in manifest, "Missing prosody in manifest"
    assert "groove" in manifest, "Missing groove in manifest"
    
    print(f"  ✅ Generated persona manifest:")
    print(f"     WPM:     {manifest['cadence']['mean_wpm']:.0f}")
    print(f"     F0:      {manifest['prosody']['mean_f0']:.0f}Hz")
    print(f"     BPM:     {manifest['groove']['conversational_bpm']:.0f}")

    # Test manifest publishing
    success = bridge.publish_persona_bottle()
    assert success, "Failed to publish persona bottle"
    print(f"  ✅ Published persona manifest bottle")

    bridge.reset()
    shutil.rmtree(test_dir)
    return True


def main():
    """Run all integration tests"""
    print(f"\n{'='*60}")
    print("  OPENMILE BRIDGE — Full Pipeline Integration Tests")
    print(f"{'='*60}\n")

    tests = [
        ("Extractor", test_extractor),
        ("MIDI Mapping", test_midi_mapping),
        ("I2I Bottles", test_i2i_bottles),
        ("Persona Integration", test_persona_integration),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            result = test_fn()
            if result:
                print(f"  ✅ {name}: PASSED")
                passed += 1
        except Exception as e:
            print(f"  ❌ {name}: FAILED — {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()

    print(f"{'='*60}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
