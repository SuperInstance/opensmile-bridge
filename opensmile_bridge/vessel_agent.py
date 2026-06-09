#!/usr/bin/env python3
"""
OpenSMILE Bridge — Fleet Vessel Agent
Deployable as a fleet I2I vessel that publishes heartbeat + status + feature data.

Architecture:
    ┌─────────────────────────────────────────────┐
    │  VesselAgent                                │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
    │  │ WebSocket │  │ I2I      │  │ Persona  │  │
    │  │ Server     │  │ Publisher│  │ Tracker  │  │
    │  └──────────┘  └──────────┘  └──────────┘  │
    │  ┌──────────┐  ┌──────────┐                  │
    │  │ Health   │  │ MIDI     │                  │
    │  │ Check    │  │ Mapper   │                  │
    │  └──────────┘  └──────────┘                  │
    └─────────────────────────────────────────────┘
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, Set

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from opensmile_bridge.config import (
    PORT, I2I_ENABLED, I2I_VESSEL_DIR as VESSEL_DIR, HEARTBEAT_INTERVAL,
    PERSONA_TRACKING, MIDI_ENABLED
)
from opensmile_bridge.websocket_server import OpenSmileBridgeServer
from opensmile_bridge.extractor import OpenSmileExtractor
from opensmile_bridge.midi_mapper import MidiMapper
from opensmile_bridge.i2i_integration import I2IManager
from opensmile_bridge.persona_integration import PersonaIntegrationBridge

logger = logging.getLogger(__name__)


class FleetVesselAgent:
    """
    Full fleet vessel agent for the OpenSMILE Bridge.
    Runs WebSocket server + I2I publishing + persona tracking + health checks.
    """

    def __init__(self, vessel_name: str = "opensmile-bridge"):
        self.vessel_name = vessel_name
        self.vessel_dir = Path(VESSEL_DIR) / vessel_name
        
        # Vessel directories
        self.incoming_dir = self.vessel_dir / "incoming"
        self.outgoing_dir = self.vessel_dir / "outgoing"
        self.processed_dir = self.vessel_dir / "processed"
        
        # Create vessel directories
        for d in [self.incoming_dir, self.outgoing_dir, self.processed_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Components
        self.ws_server: Optional[OpenSmileBridgeServer] = None
        self.i2i_manager: Optional[I2IManager] = None
        self.persona_tracker: Optional[PersonaIntegrationBridge] = None
        self.extractor: Optional[OpenSmileExtractor] = None

        # State
        self.running = False
        self.last_features: Dict[str, Any] = {}
        self.client_count: int = 0
        self.total_frames: int = 0
        self.start_time: float = time.time()

    async def start(self):
        """Start all vessel agent components."""
        self.running = True
        self.start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"  🚀 {self.vessel_name.upper()} FLEET VESSEL AGENT")
        print(f"{'='*60}")
        
        # 1. Initialize I2I
        if I2I_ENABLED:
            self.i2i_manager = I2IManager()
            self._publish_agent_hello()
            print(f"  ✅ I2I Integration: enabled ({self.outgoing_dir})")

        # 2. Initialize persona tracker
        if PERSONA_TRACKING:
            self.persona_tracker = PersonaIntegrationBridge(vessel_dir=str(self.vessel_dir))
            print(f"  ✅ Persona Tracking: enabled")
        
        # 3. Initialize extractor
        self.extractor = OpenSmileExtractor()
        print(f"  ✅ OpenSMILE Extractor: ready")
        
        # 4. Start WebSocket server
        self.ws_server = OpenSmileBridgeServer(port=PORT)
        print(f"  ✅ WebSocket Server: ws://0.0.0.0:{PORT}")
        
        # 5. Publish initial status
        self._publish_status("initialized")
        
        print(f"{'='*60}")
        print(f"  Bridge ready. Send audio to ws://0.0.0.0:{PORT}")
        print(f"  Vessel: {self.outgoing_dir}")
        print(f"{'='*60}\n")
        
        # Start background tasks
        await asyncio.gather(
            self.ws_server.start(),
            self._heartbeat_loop(),
            self._incoming_watcher(),
        )

    def _publish_agent_hello(self):
        """Publish agent announcement to vessel."""
        hello = {
            "type": "agent_hello",
            "agent": self.vessel_name,
            "version": "2.0.0",
            "services": ["websocket", "i2i", "persona", "midi"],
            "port": PORT,
            "streaming": True,
            "features": ["eGeMAPSv02", "25_lld", "persona_profiling"],
            "started_at": time.time(),
        }
        self._write_bottle("agent_hello", hello)

    def _publish_status(self, status: str):
        """Publish agent status to vessel."""
        uptime = time.time() - self.start_time
        status_msg = {
            "type": "agent_status",
            "agent": self.vessel_name,
            "status": status,
            "uptime_seconds": uptime,
            "clients": self.client_count,
            "frames_processed": self.total_frames,
            "last_features": list(self.last_features.keys())[:5],
        }
        self._write_bottle("status", status_msg)

    def _write_bottle(self, bottle_type: str, data: Dict[str, Any]):
        """Write a bottle to outgoing vessel directory."""
        if not self.i2i_manager:
            return
        try:
            bottle_id = f"{bottle_type}-{int(time.time() * 1000000)}"
            bottle = {
                "id": bottle_id,
                "type": bottle_type,
                "agent": self.vessel_name,
                "timestamp": time.time(),
                "data": data,
            }
            path = self.outgoing_dir / f"{bottle_id}.json"
            path.write_text(json.dumps(bottle, indent=2))
            logger.debug(f"📤 Published bottle {bottle_id}")
        except Exception as e:
            logger.error(f"Failed to write bottle: {e}")

    async def _heartbeat_loop(self):
        """Periodic heartbeat publishing."""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            self._publish_status("running")

    async def _incoming_watcher(self):
        """Watch for incoming bottles and process commands."""
        while self.running:
            await asyncio.sleep(1.0)
            # Check for new incoming bottles
            bottles = sorted(self.incoming_dir.glob("*.json"))
            for bottle_path in bottles:
                try:
                    self._process_bottle(bottle_path)
                except Exception as e:
                    logger.error(f"Bottle processing error: {e}")
                # Move to processed
                dest = self.processed_dir / bottle_path.name
                bottle_path.rename(dest)

    def _process_bottle(self, bottle_path: Path):
        """Process an incoming command bottle."""
        bottle = json.loads(bottle_path.read_text())
        cmd = bottle.get("data", {}).get("command", "")
        
        match cmd:
            case "ping":
                self._write_bottle("pong", {
                    "reply_to": bottle.get("id", ""),
                    "agent": self.vessel_name,
                    "status": "alive",
                    "uptime": time.time() - self.start_time,
                    "features_available": list(self.last_features.keys())[:5],
                })
                
            case "get_features":
                self._write_bottle("features_response", {
                    "reply_to": bottle.get("id", ""),
                    "features": self.last_features,
                })
                
            case "get_status":
                self._write_bottle("status_response", {
                    "reply_to": bottle.get("id", ""),
                    "uptime": time.time() - self.start_time,
                    "clients": self.client_count,
                    "frames": self.total_frames,
                })
                
            case _:
                pass  # Unknown command

    def stop(self):
        """Stop the vessel agent gracefully."""
        self.running = False
        self._publish_status("stopped")
        print(f"\n🛑 {self.vessel_name} vessel agent stopped")
        print(f"   Uptime: {(time.time() - self.start_time):.0f}s")
        print(f"   Frames: {self.total_frames}")
        print(f"   Clients: {self.client_count}")


async def run_vessel_agent():
    """Run the fleet vessel agent."""
    agent = FleetVesselAgent()
    try:
        await agent.start()
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print("\n💁 Received interrupt, shutting down...")
    finally:
        agent.stop()


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="OpenSMILE Bridge Fleet Vessel Agent")
    parser.add_argument("--port", type=int, default=PORT, help="WebSocket port")
    parser.add_argument("--no-i2i", action="store_true", help="Disable I2I")
    parser.add_argument("--no-persona", action="store_true", help="Disable persona tracking")
    parser.add_argument("--flush-vessel", action="store_true", help="Clear vessel directory on start")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    if args.flush_vessel:
        vessel_dir = Path(VESSEL_DIR) / "opensmile-bridge"
        import shutil
        for d in [vessel_dir / "incoming", vessel_dir / "outgoing", vessel_dir / "processed"]:
            if d.exists():
                shutil.rmtree(d)
                d.mkdir(parents=True)
                print(f"🧹 Flushed {d}")
    
    asyncio.run(run_vessel_agent())


if __name__ == "__main__":
    main()
