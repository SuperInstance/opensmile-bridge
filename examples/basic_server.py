#!/usr/bin/env python3
"""
Basic OpenSMILE Bridge Server Example

Simple server that starts a WebSocket bridge and prints extracted features.
"""

import asyncio
import json
from opensmile_bridge.websocket_server import OpenSmileBridgeServer


def feature_callback(features):
    """Simple callback to print features when they're extracted"""
    print(f"\n🎵 Extracted features: ")
    print(f"   F0:          {features.get('f0_hz', 0):.1f}Hz")
    print(f"   Loudness:    {features.get('loudness', 0):.1f}dB")
    print(f"   Jitter:      {features.get('jitter', 0):.4f}")
    print(f"   HNR:         {features.get('hnr', 0):.1f}dB")
    print(f"   Voicing:     {features.get('voicing_probability', 0):.2f}")
    
    # Print MIDI CC mapping
    if 'midi_cc' in features:
        print(f"   MIDI CC:     {json.dumps(features['midi_cc'], indent=2)}")


async def main():
    print("🚀 Starting Basic OpenSMILE Bridge Server")
    print("   Listening on ws://0.0.0.0:8765")
    print("   Press Ctrl+C to stop")
    
    # Create server with custom feature callback
    server = OpenSmileBridgeServer(port=8765)
    
    # Add our callback
    server.feature_callback = feature_callback
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
