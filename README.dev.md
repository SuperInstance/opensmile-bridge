# OpenSMILE Bridge Developer Onboarding

## Welcome to the OpenSMILE Bridge development team! This guide will help you get started contributing to the modular OpenSMILE bridge system for the SuperInstance fleet.

---

## 🚀 Quick Start for Development

### 1.  **Install Dependencies**

```bash
# Install development dependencies
pip install -e .[dev]

# Install system packages (Ubuntu/Debian
sudo apt-get install portaudio19-dev libav-tools
```

# Install opensmile system-wide
# (if pip install doesn't include the Python package
pip install opensmile
```

### 2.  **Run Locally

#### Basic Development Server
```bash
python -m opensmile_bridge.websocket_server --debug
```

#### With I2I publishing enabled
```bash
export OPENSMILE_BRIDGE_I2I_ENABLED=true
export OPENSMILE_BRIDGE_VESSEL_DIR=/tmp/test-i2i
python -m opensmile_bridge.websocket_server --debug
```

### 3.  **Test the System**

#### Open two terminals:

**Terminal 1: Run the bridge server
```bash
python -m opensmile_bridge.websocket_server --port 8766
```

**Terminal 2: Send test audio**
```bash
pip install soundfile
python examples/audio_file_processor.py --audio-file test.wav
```

Or use a WebSocket client directly:
```bash
wscat -c ws://localhost:8766
# Send binary audio data with: binary mode on
```

---

## 🧱 Architecture Deep Dive

### Core Component Overview

| Module | Responsibility | API Docs |
|---------|----------------|----------|
| **config.py | Centralized, environment-based configuration | Fully documented |
| **extractor.py** | Audio → OpenSMILE feature extraction | Streaming + batch modes |
| **midi_mapper.py** | Feature → MIDI CC mapping with normalization | Supports custom mappings |
| **websocket_server.py** | WebSocket transport for audio + client handling | Full async support |
| **i2i_integration.py** | I2I bottle publishing/consuming | Full I2I v2.1 spec |

### Lifecycle of a Feature

1.  **Audio Ingest:
    - Raw audio chunks received via WebSocket or file
    - Feeds into `OpenSmileExtractor`

2.  **Feature Extraction**:
    - OpenSMILE processes the audio into eGeMAPS features
    - Features are parsed and normalized

3.  **Mapping & Publishing:
    - Features are mapped to MIDI CC messages
    - MIDI messages are packed into I2I bottles
    - Bottles published to vessel directory

4.  **Fleet Delivery**:
    - All fleet agents can subscribe to the bridge's vessel directory
    - Features are immediately usable downstream

---

## 🎯 Adding New Features

### How to Add a New OpenSMILE Feature

1.  **Update the feature mapping in `config.py`**:
    ```python
    FEATURE_MAPPING: dict[str, str] = {
        # Existing mappings
        'new_feature_sma3': 'friendly_name',
    }
    ```

2.  **Add MIDI CC mapping in `midi_mapper.py`**:
    ```python
    MIDI_CC_MAPPING: dict[str, int] = {
        'friendly_name': 123,  # CC number
    }
    ```

3.  **Add normalization logic**:
    Add a case in the `_normalize_value` method in `midi_mapper.py:
    ```python
    match feature_name:
        case "new_feature":
            # Your normalization logic
            return np.clip(value / 100.0, 0.0, 1.0)
    ```

4.  **Test your changes**:
    ```bash
    python tests/test_extractor.py
    python tests/test_midi_mapper.py
    ```

---

## ✅ Testing Guidelines

### Test Suite Structure

```
tests/
├── test_extractor.py              # Test feature extraction
├── test_midi_mapper.py          # Test MIDI mapping
├── test_websocket_server.py      # Test WebSocket server
├── test_i2i_integration.py        # Test I2I publishing
└── test_full_pipeline.py        # End-to-end pipeline test
```

### Run All Tests

```bash
pytest tests/ --verbose
```

### Test Coverage

```bash
pytest tests/ --cov=opensmile_bridge --cov-report=html
```

---

## 🚢 Fleet Deployment

### Deployment Patterns for SuperInstance

1.  **Standalone Container**:
    Deploy as a separate service in the fleet

2.  **Embedded in Another Agent:
    Import as a module directly into other agents like persona-engine or opensmile-bridge

3.  **Sidecar Container**:
    Run as a sidecar to other fleet services

### Environment Variables for Production

```bash
# Production I2I fleet deployment
export OPENSMILE_BRIDGE_I2I_ENABLED=true
export OPENSMILE_BRIDGE_VESSEL_DIR=/opt/construct/i2i-vessel
export OPENSMILE_BRIDGE_LOG_LEVEL=INFO
export OPENSMILE_BRIDGE_SPEAKER_ID=opensmile-bridge-production

# Run server on standard port
export OPENSMILE_BRIDGE_PORT=8765
```

---

## 🐛 Common Issues & Fixes

### 1.  OpenSMILE Not Found

**Error:** `ImportError: No module named 'opensmile'`

**Fix:**
```bash
pip install opensmile
```

### 2.  Streaming not available

**Error:** `WARNING: Streaming mode not available

**Fix:**
Streaming OpenSMILE requires native libraries. Install system libraries:
- Ubuntu/Debian: `sudo apt-get install libsox-dev`
- macOS: `brew install sox`

### 3.  I2I publishing failed

**Error:** `Failed to initialize I2I

**Fix:**
Ensure the vessel directory exists and has correct permissions:
```bash
mkdir -p /tmp/i2i-vessel/incoming /tmp/i2i-vessel/outgoing
chmod 755 /tmp/i2i-vessel
```

### 4.  Audio format issues

**Problem:** No features being extracted

**Fix:**
Ensure audio is:
- 16-bit PCM
- Mono channel
- 16000 Hz sample rate

---

## 📖 API Reference

### OpenSmileExtractor

```python
class OpenSmileExtractor:
    def __init__(self, use_streaming: bool = True):
        """Initialize with optional streaming mode"""
    
    def feed_audio(self, audio_chunk: np.ndarray) -> None:
        """Feed audio data for processing"""
    
    def extract(self) -> Optional[Dict[str, Any]] -> Dict[str, Any]:
        """Get processed features"""
    
    def clear(self) -> None:
        """Clear buffers"""
```

### I2IManager

```python
class I2IManager:
    def publish_bottle(self, bottle: Dict[str, Any]) -> bool:
        """Publish an I2I bottle"""
    
    def publish_features(self, features: Dict[str, Any]) -> bool:
        """Publish voice features directly"""
```

---

## 🎨 Contributing Standards

1.  All new features must include tests
2.  Follow the existing code style (PEP 8
3.  Document all new functions/classes
4.  Update this onboarding guide when changing core functionality
5.  I2I compliance must be maintained per the fleet specs
6.  Use type annotations for all API functions

---

## 💡 Useful Resources

- [OpenSMILE Documentation](https://audeering.github.io/opensmile/)
- [eGeMAPS Feature Set](https://audeering.com/technology/egemaps/)
- [I2I Protocol Specification
- [SuperInstance Fleet Docs](https://github.com/construct-coordination)

---

## 📞 Support

For questions, use the fleet communication channels:
1.  **Discord server: https://discord.gg/SuperInstance
2.  **GitHub issues
3.  **Fleet sync meetings every Wednesday 14:00 UTC

*Note: If you're reading this, you're part of the Oracle2 team! 🦀

---

Happy coding! The fleet depends on you.
