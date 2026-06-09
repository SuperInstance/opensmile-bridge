#!/usr/bin/env python3
"""
Fleet Runner — Deploy OpenSMILE Bridge as a full I2I fleet agent.

Deploys:
  1. WebSocket server for live audio (port 8765)
  2. I2I vessel integration (publishes VOICE_FEATURES bottles)
  3. Persona engine integration (cadence/prosody profiling)
  4. Fleet-midi-pulse timing sync
  5. Ghost-track-bridge reharmonization feed

Usage:
    python -m opensmile_bridge.runner                  # full deployment
    python -m opensmile_bridge.runner --no-i2i          # standalone mode
    python -m opensmile_bridge.runner --no-persona      # no persona profiling
    python -m opensmile_bridge.runner --flush-vessel    # clear vessel before start
"""

import asyncio
import argparse
import json
import logging
import os
import sys
import signal
import shutil
from pathlib import Path
from typing import Optional

from .websocket_server import OpenSmileBridgeServer
from .midi_mapper import MidiMapper
from .i2i_integration import I2IManager
from .persona_integration import PersonaIntegrationBridge
from .config import (
    PORT, SAMPLE_RATE, I2I_VESSEL_DIR, I2I_SPEAKER_ID,
    I2I_ENABLED, LOG_LEVEL, GHOST_BRIDGE_URL, TMINUS_DISPATCHER_URL
)


class FleetRunner:
    """
    Deploys and coordinates all bridge subsystems
    """

    def __init__(
        self,
        port: int = PORT,
        enable_i2i: bool = I2I_ENABLED,
        enable_persona: bool = True,
        vessel_dir: str = I2I_VESSEL_DIR,
        speaker_id: str = I2I_SPEAKER_ID,
        flush_vessel: bool = False,
    ):
        self.port = port
        self.enable_i2i = enable_i2i
        self.enable_persona = enable_persona
        self.vessel_dir = Path(vessel_dir)
        self.speaker_id = speaker_id
        self.flush_vessel = flush_vessel

        # Component references
        self.server: Optional[OpenSmileBridgeServer] = None
        self.i2i_manager: Optional[I2IManager] = None
        self.persona_bridge: Optional[PersonaIntegrationBridge] = None

        # Health state
        self.healthy = True
        self.frame_count = 0

        # Set up logging
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        )
        self.log = logging.getLogger("fleet-runner")

    def setup(self):
        """Prepare vessel directories and initialize components"""
        self.log.info("⚙️  Setting up Fleet Runner...")

        # Flush vessel if requested
        if self.flush_vessel and self.vessel_dir.exists():
            shutil.rmtree(self.vessel_dir)
            self.log.info(f"🗑️  Flushed vessel: {self.vessel_dir}")

        # Create vessel directory structure
        for sub in ["incoming", "outgoing", "processed"]:
            (self.vessel_dir / sub).mkdir(parents=True, exist_ok=True)

        # Initialize WebSocket server
        self.server = OpenSmileBridgeServer(port=self.port)

        # Initialize I2I manager
        if self.enable_i2i:
            self.i2i_manager = I2IManager(
                vessel_dir=str(self.vessel_dir),
                speaker_id=self.speaker_id
            )
            self.log.info(f"✅ I2I manager ready at {self.vessel_dir}")

        # Initialize persona bridge
        if self.enable_persona:
            self.persona_bridge = PersonaIntegrationBridge(
                vessel_dir=str(self.vessel_dir),
                speaker_id=self.speaker_id
            )
            self.log.info("✅ Persona bridge ready")

        self.healthy = True
        self.log.info(f"✅ Fleet Runner initialized (port={self.port}, "
                      f"i2i={self.enable_i2i}, persona={self.enable_persona})")

    async def _health_check_loop(self):
        """Periodically check and report health"""
        while self.healthy:
            await asyncio.sleep(30)
            status = {
                "service": "opensmile-bridge",
                "speaker_id": self.speaker_id,
                "port": self.port,
                "i2i_enabled": self.enable_i2i,
                "persona_enabled": self.enable_persona,
                "clients_connected": len(self.server.clients) if self.server else 0,
                "frames_processed": self.frame_count,
                "vessel_dir": str(self.vessel_dir),
            }

            # Publish health to I2I
            if self.i2i_manager:
                bottle = self.i2i_manager.create_bottle(
                    bottle_type="HEALTH",
                    payload=status | {"timestamp": asyncio.get_event_loop().time()},
                    context={"source": "opensmile-bridge", "type": "health"}
                )
                self.i2i_manager.publish_bottle(bottle)

    async def _persona_bottle_loop(self):
        """Periodically publish persona manifests from voice tracking"""
        while self.healthy and self.persona_bridge:
            await asyncio.sleep(15)  # Every 15 seconds
            if self.persona_bridge._frame_timestamps:
                success = self.persona_bridge.publish_persona_bottle()
                if success:
                    self.log.debug("📦 Published persona manifest bottle")
                    self.persona_bridge.reset()

    async def _feature_bottle_loop(self):
        """Periodically publish accumulated VOICE_FEATURES bottles"""
        last_features = None
        while self.healthy:
            await asyncio.sleep(0.5)  # Every 500ms
            features = getattr(self.server.extractor, 'last_features', None) if self.server else None
            if features and features != last_features:
                last_features = features.copy()
                self.frame_count += 1

                if self.i2i_manager:
                    self.i2i_manager.publish_features(last_features)

    async def run(self):
        """Start all subsystems"""
        self.setup()

        self.log.info("🚀 Deploying OpenSMILE Bridge to fleet...")
        self.log.info(f"   WebSocket API:     ws://0.0.0.0:{self.port}")
        self.log.info(f"   I2I Vessel:        {self.vessel_dir}")
        self.log.info(f"   Pipeline targets:")
        self.log.info(f"     → ghost-track:   {GHOST_BRIDGE_URL}")
        self.log.info(f"     → tminus:        {TMINUS_DISPATCHER_URL}")

        # Start background loops
        tasks = [
            asyncio.create_task(self.server.start()) if self.server else None,
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._feature_bottle_loop()),
        ]

        if self.persona_bridge:
            tasks.append(asyncio.create_task(self._persona_bottle_loop()))

        # Wait for completion (or interrupt)
        try:
            await asyncio.gather(*[t for t in tasks if t is not None])
        except asyncio.CancelledError:
            pass
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown"""
        self.healthy = False
        self.log.info("🛑 Shutting down fleet runner...")
        if self.server:
            await self.server.stop()


async def main():
    parser = argparse.ArgumentParser(
        description="Fleet Runner: Deploy OpenSMILE Bridge as full I2I agent"
    )
    parser.add_argument("--port", "-p", type=int, default=PORT,
                        help=f"WebSocket port (default: {PORT})")
    parser.add_argument("--no-i2i", action="store_true",
                        help="Disable I2I vessel integration")
    parser.add_argument("--no-persona", action="store_true",
                        help="Disable persona engine profiling")
    parser.add_argument("--vessel-dir", type=str, default=I2I_VESSEL_DIR,
                        help="I2I vessel directory")
    parser.add_argument("--speaker-id", type=str, default=I2I_SPEAKER_ID,
                        help="Speaker ID for I2I bottles")
    parser.add_argument("--flush-vessel", action="store_true",
                        help="Clear vessel before starting")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Set env overrides
    if args.no_i2i:
        os.environ["OPENSMILE_BRIDGE_I2I_ENABLED"] = "false"
    else:
        os.environ["OPENSMILE_BRIDGE_I2I_ENABLED"] = "true"

    runner = FleetRunner(
        port=args.port,
        enable_i2i=not args.no_i2i,
        enable_persona=not args.no_persona,
        vessel_dir=args.vessel_dir,
        speaker_id=args.speaker_id,
        flush_vessel=args.flush_vessel,
    )

    try:
        await runner.run()
    except KeyboardInterrupt:
        print("\n🛑 Interrupted. Shutting down...")
        await runner.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
