#!/usr/bin/env python3
"""
OpenSMILE Bridge WebSocket Server
Modular WebSocket server that accepts audio streams and publishes voice features
"""

import asyncio
import json
import numpy as np
import websockets
from typing import Dict, Any, Optional, List
from pathlib import Path
import time

from .extractor import OpenSmileExtractor
from .midi_mapper import MidiMapper
from .i2i_integration import I2IManager
from .config import PORT, SAMPLE_RATE, I2I_ENABLED, LOG_LEVEL


# Global state for last features (for bottle responses)
last_features: Dict[str, Any] = {}


class OpenSmileBridgeServer:
    """
    WebSocket server for OpenSMILE feature extraction
    
    Accepts audio chunks via WebSocket, extracts features, maps to MIDI CC,
    and publishes to fleet via I2I protocol.
    """

    def __init__(self, port: int = PORT):
        """
        Initialize OpenSMILE WebSocket Bridge Server
        """
        self.port = port
        self.clients: set = set()
        self.running = False
        self.server = None
        
        # Initialize components
        self.extractor = OpenSmileExtractor()
        self.midi_mapper = MidiMapper()
        
        # Initialize I2I if enabled
        self.i2i_manager: Optional[I2IManager] = None
        if I2I_ENABLED:
            try:
                self.i2i_manager = I2IManager()
                print(f"✅ I2I integration enabled: {I2I_ENABLED}")
            except Exception as e:
                print(f"⚠️  Failed to initialize I2I: {e}")

        # Audio buffer
        self.audio_buffer: List[float] = []
        self.last_frame_time = time.time()

    async def handle_connection(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """
        Handle incoming WebSocket connection
        """
        print(f"🔌 New client connection from {websocket.remote_address}")
        self.clients.add(websocket)
        
        try:
            async for message in websocket:
                # Handle binary audio data
                if isinstance(message, bytes):
                    await self._handle_audio_chunk(message, websocket)
                
                # Handle JSON control messages
                elif isinstance(message, str):
                    await self._handle_control_message(message, websocket)
        
        except websockets.ConnectionClosed:
            print(f"👋 Client disconnected: {websocket.remote_address}")
        finally:
            self.clients.remove(websocket)

    async def _handle_audio_chunk(self, audio_data: bytes, origin_ws):
        """
        Process incoming audio chunk
        """
        try:
            # Convert bytes to numpy array
            audio_chunk = np.frombuffer(audio_data, dtype=np.float32)
            
            # Feed to extractor
            self.extractor.feed_audio(audio_chunk)
            
            # Get processed features
            features = self.extractor.extract()
            
            if features:
                global last_features
                last_features = features.copy()
                
                # Map to MIDI CC
                midi_cc = self.midi_mapper.map_all_features(features)
                features["midi_cc"] = midi_cc
                
                # Publish via I2I if enabled
                if self.i2i_manager:
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.i2i_manager.publish_features, features
                    )
                
                # Broadcast features to all connected clients
                await self._broadcast(json.dumps({
                    "type": "features",
                    "data": features,
                    "timestamp": time.time(),
                }))
                
                # Throttle logging
                if features.get("frame", 0) % 100 == 0:
                    print(f"🎵 Extracted {len(features)} features @ frame {features.get('frame', 0)}")
        
        except Exception as e:
            print(f"⚠️  Audio processing error: {e}")
            import traceback
            traceback.print_exc()

    async def _handle_control_message(self, message: str, origin_ws):
        """
        Handle JSON control messages from clients
        """
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            match message_type:
                case "ping":
                    await origin_ws.send(json.dumps({"type": "pong", "timestamp": time.time()}))
                    
                case "get_features":
                    # Respond with current features
                    await origin_ws.send(json.dumps({
                        "type": "features",
                        "data": last_features,
                        "timestamp": time.time()
                    }))
                    
                case "set_config":
                    # Update configuration
                    await self._handle_config_update(data.get("config", {}))
                    
                case "request_i2i":
                    # Manually request I2I publishing
                    if self.i2i_manager and last_features:
                        self.i2i_manager.publish_features(last_features)
                        await origin_ws.send(json.dumps({"type": "i2i_published", "success": True}))
                
                case _:
                    print(f"⚠️  Unknown control message: {message_type}")
                    
        except json.JSONDecodeError:
            print("⚠️  Invalid JSON control message")

    async def _handle_config_update(self, config: Dict[str, Any]):
        """
        Handle server configuration updates
        """
        # Update extractor
        if "sample_rate" in config:
            self.extractor = OpenSmileExtractor(sample_rate=config["sample_rate"])
        
        print(f"✅ Updated configuration: {config}")

    async def _broadcast(self, message: str):
        """
        Broadcast message to all connected clients
        """
        disconnected = []
        for client in self.clients:
            try:
                await client.send(message)
            except Exception:
                disconnected.append(client)
        
        # Clean up disconnected clients
        for client in disconnected:
            if client in self.clients:
                self.clients.remove(client)

    async def start(self):
        """
        Start the WebSocket server
        """
        self.server = await websockets.serve(
            self.handle_connection,
            "0.0.0.0",
            self.port
        )
        self.running = True
        print(f"🚀 OpenSMILE Bridge WebSocket server running on ws://0.0.0.0:{self.port}")
        
        # Keep server running
        await self.server.wait_closed()

    async def stop(self):
        """
        Stop the WebSocket server gracefully
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.running = False
        print("🛑 OpenSMILE Bridge server stopped")


async def run_server(port: int = PORT):
    """
    Run the OpenSMILE bridge server
    """
    server = OpenSmileBridgeServer(port)
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n💁 Received interrupt, shutting down...")
        await server.stop()


def main():
    """
    CLI entry point
    """
    import argparse
    parser = argparse.ArgumentParser(description="OpenSMILE Feature Bridge WebSocket Server")
    parser.add_argument("--port", "-p", type=int, default=PORT,
                        help=f"WebSocket port (default: {PORT})")
    parser.add_argument("--disable-i2i", action="store_true",
                        help="Disable I2I fleet integration")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    asyncio.run(run_server(args.port))


if __name__ == "__main__":
    main()
