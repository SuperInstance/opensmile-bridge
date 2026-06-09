# OpenSMILE Bridge - Fleet Voice Feature Module

<div align="center">

**Production-grade modular voice feature extraction for the SuperInstance fleet**

[![I2I Protocol](https://img.shields.io/badge/protocol-I2I%20v2.1-blue)](#i2i-integration)
[![WebSocket](https://img.shields.io/badge/transport-WebSocket%20%2F%20JSON-green)](#usage)
[![OpenSMILE](https://img.shields.io/badge/extractor-OpenSMILE%20eGeMAPSv02-orange)](#features)
[![Status](https://img.shields.io/badge/status-stable-yellow)]()

</div>

---

## What This Is

This is a completely refactored, modular OpenSMILE voice feature bridge designed for integration into the SuperInstance fleet ecosystem. It extracts production-grade voice characteristics from audio streams (live or recorded), maps them to MIDI CC messages, and publishes them as I2I bottles for other fleet agents to consume.

This replaced the older monolithic bridge code with a clean, maintainable architecture that fits perfectly with our modular agent system.

---

## Core Features

### 🎤 **Complete Voice Feature Extraction**
- 25+ eGeMAPS v02 Low Level Descriptors (F0, formants, jitter, shimmer, HNR, MFCCs, brightness...)
- Live streaming processing for real-time audio streams
- Batch processing for recorded files
- Full MIDI CC mapping for all key features

### 🧩 **Modular Design**
- `extractor.py` - Standalone OpenSMILE feature extraction (streaming + batch)
- `midi_mapper.py` - Feature → MIDI CC conversion with normalization
- `websocket_server.py` - WebSocket server for live audio streams
- `i2i_integration.py` - Full I2I fleet protocol support
- `config.py` - Centralized configuration system

### 🚢 **Built for the Fleet**
- Seamless integration with SuperInstance I2I bottle protocol
- Publishes voice features directly to the fleet vessel directory
- Compatible with fleet-midi-pulse timing system
- Works with ghost-track-bridge and tminus-dispatcher

---

## Architecture

```
Audio Source → [WebSocket Server] → [OpenSMILE Extractor] → [MIDI Mapper] → [I2I Publisher]
    (mic,      or                (streaming or       (feature →        (directly to fleet
     file)     audio chunks)      batch processing)    MIDI CC)          vessel/broadcast
```

### Fleet Integration Flow
```
1. Browser mic → WebSocket → OpenSMILE Bridge
2. OpenSMILE extracts 25 eGeMAPS features
3. Features mapped to MIDI CC
4. Features published as I2I `VOICE_FEATURES` bottles
5. Fleet agents subscribe to feature updates:
   - ghost-track-bridge (reharmonization)
   - tminus-dispatcher (timing)
   - fleet-midi-pulse (groove)
   - persona-engine (voice profiling)
```

---

## Quick Start

### Install Dependencies

```bash
# Install from PyPI (coming soon)
pip install opensmile-bridge

# OR install from source
pip install -e .
```

### Run the Basic WebSocket Server

```bash
python -m opensmile_bridge.websocket_server --port 8765
```

This starts:
- A WebSocket server on port 8765 that accepts audio chunks
- Automatic OpenSMILE feature extraction
- MIDI CC mapping
- Optional I2I fleet publishing

### Use the Standalone Extractor

```python
from opensmile_bridge.extractor import OpenSmileExtractor
import numpy as np

# Initialize extractor
extractor = OpenSmileExtractor()

# Generate test audio
sample_rate = 16000
duration = 1
freq = 440
t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
audio = np.sin(2 * np.pi * freq * t)

# Process audio
extractor.feed_audio(audio)
features = extractor.extract()

print("Extracted features:", features)
```

### Use MIDI Mapping

```python
from opensmile_bridge.midi_mapper import MidiMapper

mapper = MidiMapper()

# Map individual features
f0_hz = 440.0
cc_info = mapper.map_feature_to_cc("loudness", -20.0)
print(f"Loudness → CC{cc_info[0]}: {cc_info[1]}")

# Map all features
all_cc = mapper.map_all_features(features)
print("All MIDI CC:", all_cc)
```

### Run as a Fleet Agent

Start the bridge with full I2I fleet integration:

```bash
EXPORT OPENSMILE_BRIDGE_I2I_ENABLED=true
EXPORT OPENSMILE_BRIDGE_VESSEL_DIR=/tmp/i2i-vessel
python -m opensmile_bridge.websocket_server
```

---

## Key Features & MIDI Mapping

| OpenSMILE Feature | MIDI CC # | What It Controls | Typical Range |
|-------------------|-----------|--------------------|---------------|
| Loudness | 7 | Volume | -60 → 0dB → 0 → 127 |
| Jitter | 16 | Vocal Roughness/Distortion | 0 → 0.05 → 0 → 127 |
| Shimmer |17 | Amplitude Instability/Tremolo | 0 → 0.05dB → 0 → 127 |
| HNR |2 | Breathiness Control | 0 → 40dB → 0 → 127 |
| Alpha Ratio (Vowel) |74 | Vowel Openness/Cutoff | 0 → 1 → 0 → 127 |
| Spectral Flux |75 | Brightness | 0 → 1 → 0 → 127 |
| Voicing Probability |70 | Expression | 0 → 1 → 0 → 127 |
| F0 (Pitch) |1 | Fundamental Frequency | 80Hz → 1100Hz → see pitch bend |

---

## Fleet Integration

### I2I Bottle Support

This bridge fully implements the SuperInstance I2I protocol:

**Incoming Bottles Handled:**
- `FEATURE_REQUEST` - Request current voice features
- `CONFIG_REQUEST` - Request bridge configuration
- `COMMAND` - General commands (ping, reset, etc.)

**Outgoing Bottles Published:**
- `FEATURES` - Raw voice features every frame

**Bottle Payload Example:**
```json
{
  "type": "VOICE_FEATURES",
  "data": {
    "f0_hz": 440.0,
    "loudness": -20.0,
    "jitter": 0.01,
    "hnr": 20.0,
    "midi_cc": {7: 80, 16: 25}
  },
  "speaker_id": "opensmile-bridge-1",
  "frame": 1234,
  "timestamp": 1717881600
}
```

### Fleet Compatibility

- ✅ `fleet-midi-pulse` - Timing/groove integration
- ✅ `ghost-track-bridge` - Reharmonization
- ✅ `tminus-dispatcher` - Event scheduling
- ✅ `persona-engine` - Voice profile extraction
- ✅ `superinstance-toolchain` - Full pipeline support

---

## Command Line Tools

### Basic Bridge Server
```bash
python -m opensmile_bridge.websocket_server --port 8765
```

### Debug Mode
```bash
python -m opensmile_bridge.websocket_server --debug
```

### Custom Port & Disabled I2I
```bash
python -m opensmile_bridge.websocket_server --port 9000 --disable-i2i
```

### Feature Extraction CLI
```bash
python -m opensmile_bridge.extractor --audio-file test.wav
```

---

## Configuration

All configuration can be set via environment variables:

| Variable | Description | Default |
|-----------|-------------|---------|
| `OPENSMILE_BRIDGE_PORT` | WebSocket port | 8765 |
| `OPENSMILE_BRIDGE_I2I_ENABLED` | Enable I2I integration | False |
| `OPENSMILE_BRIDGE_VESSEL_DIR` | I2I vessel directory | `/tmp/i2i-vessel` |
| `OPENSMILE_BRIDGE_LOG_LEVEL` | Log level | `INFO` |
| `OPENSMILE_FEATURE_SET` | OpenSMILE feature set | `eGeMAPSv02` |
| `OPENSMILE_FEATURE_LEVEL` | OpenSMILE feature level | `LowLevelDescriptors` |

---

## Contributing

### Project Structure

```
opensmile-bridge-v2/
├── opensmile_bridge/             # Modular library
│   ├── __init__.py
│   ├── config.py               # Centralized configuration
│   ├── extractor.py              # OpenSMILE feature processing
│   ├── midi_mapper.py          # Feature → MIDI CC mapping
│   ├── websocket_server.py      # WebSocket transport
│   └── i2i_integration.py        # I2I fleet integration
├── examples/                     # Usage examples
│   ├── basic_server.py
│   ├── i2i_agent.py
│   └── audio_file_processor.py
├── cli/                          # CLI tools
│   ├── bridge.py
│   └── onboarding.py
├── README.md                      # This file
├── README.dev.md                  # Developer onboarding
└── requirements.txt              # Dependencies
```

---

## Developer Onboarding

See [README.dev.md](./README.dev.md) for full developer documentation:
- How to add new feature mappings
- Testing guidelines
- CI/CD setup
- Fleet deployment patterns
- Common issues and fixes

---

## Related Projects

- [SuperInstance/fleet-midi-pulse](https://github.com/SuperInstance/fleet-midi-pulse) - BPM/swing/fermata timing layer
- [SuperInstance/ghost-track-bridge](https://github.com/SuperInstance/ghost-track-bridge) - Reharmonization engine
- [SuperInstance/tminus-dispatcher](https://github.com/SuperInstance/tminus-dispatcher) - Event scheduling
- [SuperInstance/persona-engine](https://github.com/SuperInstance/persona-engine) - Voice profile extraction
- [SuperInstance/A2A-native-notebookLM](https://github.com/SuperInstance/A2A-native-notebookLM) - Fleet cognitive command center

---

## License

MIT

*Built for the SuperInstance fleet • The crab inherits the shell.*
