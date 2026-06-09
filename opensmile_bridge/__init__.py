"""
OpenSMILE Bridge — modular voice feature extraction for the SuperInstance fleet.

Submodules:
    extractor       — OpenSMILE feature extraction (streaming + batch)
    midi_mapper     — Feature → MIDI CC mapping with normalization
    websocket_server — Async WebSocket server for live audio
    i2i_integration — I2I bottle protocol publishing/consuming
    persona_integration — Persona engine cadence/prosody profiling
    runner          — Fleet agent deployment runner
    config          — Centralized configuration from environment
"""

__version__ = "2.0.0"
