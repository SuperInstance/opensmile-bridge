#!/usr/bin/env python3
"""
I2I Integration for OpenSMILE Bridge
Publish extracted voice features as I2I bottles to the fleet
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone

from .config import I2I_VESSEL_DIR, I2I_SPEAKER_ID


class I2IManager:
    """
    Manages publishing and consuming I2I bottles for the OpenSMILE bridge
    """

    def __init__(
        self,
        vessel_dir: str = I2I_VESSEL_DIR,
        speaker_id: str = I2I_SPEAKER_ID
    ):
        """
        Initialize I2I integration
        
        Args:
            vessel_dir: Directory for I2I bottle storage
            speaker_id: Unique ID for this speaker/bridge
        """
        self.vessel_dir = Path(vessel_dir)
        self.speaker_id = speaker_id
        self._incoming_dir = self.vessel_dir / "incoming"
        self._outgoing_dir = self.vessel_dir / "outgoing"
        
        # Create directories if they don't exist
        self._incoming_dir.mkdir(parents=True, exist_ok=True)
        self._outgoing_dir.mkdir(parents=True, exist_ok=True)

    def create_bottle(
        self,
        bottle_type: str,
        payload: Dict[str, Any],
        recipient: str = "broadcast",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create an I2I bottle envelope
        
        Args:
            bottle_type: Type of bottle (FEATURES, COMMAND, RESPONSE)
            payload: Bottle payload data
            recipient: Recipient agent ID
            context: Optional context metadata
            
        Returns:
            Formatted I2I bottle envelope
        """
        bottle_id = f"smile-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        bottle = {
            "id": bottle_id,
            "sender": self.speaker_id,
            "recipient": recipient,
            "type": bottle_type,
            "payload": payload,
            "context": context or {},
            "timestamp": timestamp,
            "version": "i2i/1.0"
        }
        
        return {
            "bottle": bottle,
            "signature": None,
            "routing": {
                "ttl": 3600,  # 1 hour TTL
                "priority": 1
            }
        }

    def publish_bottle(self, bottle: Dict[str, Any]) -> bool:
        """
        Publish an I2I bottle to the outgoing directory
        
        Args:
            bottle: Formatted I2I bottle envelope
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bottle_id = bottle["bottle"]["id"]
            filename = f"{bottle_id}.json"
            
            # Write atomically
            temp_file = self._outgoing_dir / f".tmp.{filename}.{os.getpid()}"
            with open(temp_file, "w") as f:
                json.dump(bottle, f, indent=2)
            temp_file.rename(self._outgoing_dir / filename)
            
            print(f"📤 Published bottle {bottle_id} to {self._outgoing_dir}")
            return True
            
        except Exception as e:
            print(f"⚠️  Failed to publish bottle: {e}")
            return False

    def publish_features(self, features: Dict[str, Any]) -> bool:
        """
        Publish voice features as an I2I bottle
        
        Args:
            features: Extracted voice features
            
        Returns:
            True if successful, False otherwise
        """
        payload = {
            "type": "VOICE_FEATURES",
            "data": features,
            "speaker_id": self.speaker_id,
            "frame": features.get("frame", 0),
            "timestamp": features.get("timestamp", time.time())
        }
        
        bottle = self.create_bottle(
            bottle_type="FEATURES",
            payload=payload,
            recipient="broadcast"
        )
        
        return self.publish_bottle(bottle)

    async def process_incoming_bottles(self):
        """
        Process incoming I2I bottles
        """
        for filename in sorted(self._incoming_dir.glob("*.json")):
            try:
                with open(filename) as f:
                    bottle_envelope = json.load(f)
                    
                await self._handle_incoming_bottle(bottle_envelope)
                
                # Move to processed directory
                processed_dir = self._incoming_dir / "processed"
                processed_dir.mkdir(exist_ok=True)
                filename.rename(processed_dir / filename.name)
                
            except Exception as e:
                print(f"⚠️  Failed to process incoming bottle {filename}: {e}")
                # Move to error directory
                error_dir = self._incoming_dir / "errors"
                error_dir.mkdir(exist_ok=True)
                filename.rename(error_dir / filename.name)

    async def _handle_incoming_bottle(self, bottle_envelope: Dict[str, Any]):
        """
        Handle a single incoming bottle
        """
        bottle = bottle_envelope.get("bottle", {})
        bottle_type = bottle.get("type")
        sender = bottle.get("sender")
        payload = bottle.get("payload", {})

        print(f"📥 Received bottle {bottle.get('id')} (type={bottle_type}) from {sender}")

        match bottle_type:
            case "FEATURE_REQUEST":
                # Request for current features
                await self._handle_feature_request(bottle, payload)
                
            case "CONFIG_REQUEST":
                # Request for bridge config
                await self._handle_config_request(bottle, payload)
                
            case "COMMAND":
                # General command
                await self._handle_command(bottle, payload)
                
            case _:
                print(f"⚠️  Unknown bottle type: {bottle_type}")

    async def _handle_feature_request(self, original_bottle: Dict[str, Any], payload: Dict[str, Any]):
        """Handle request for current voice features"""
        from websocket_server import OpenSmileBridgeServer
        
        response_bottle = self.create_bottle(
            bottle_type="FEATURE_RESPONSE",
            payload={
                "request_id": original_bottle.get("id"),
                "features": getattr(OpenSmileBridgeServer, 'last_features', {})
            },
            recipient=original_bottle.get("sender")
        )
        self.publish_bottle(response_bottle)

    async def _handle_config_request(self, original_bottle: Dict[str, Any], payload: Dict[str, Any]):
        """Handle request for bridge configuration"""
        # Import here to avoid circular imports
        from .config import get_config
        
        response_bottle = self.create_bottle(
            bottle_type="CONFIG_RESPONSE",
            payload={
                "request_id": original_bottle.get("id"),
                "config": get_config()
            },
            recipient=original_bottle.get("sender")
        )
        self.publish_bottle(response_bottle)

    async def _handle_command(self, original_bottle: Dict[str, Any], payload: Dict[str, Any]):
        """Handle general command"""
        command = payload.get("command")
        print(f"🎯 Received command: {command}")
        
        # Respond to ping
        if command == "ping":
            response_bottle = self.create_bottle(
                bottle_type="COMMAND_RESPONSE",
                payload={
                    "request_id": original_bottle.get("id"),
                    "response": "pong",
                    "timestamp": time.time()
                },
                recipient=original_bottle.get("sender")
            )
            self.publish_bottle(response_bottle)


def test_i2i_integration():
    """Test I2I bottle creation and publishing"""
    print("🏃 Running I2I integration test...")
    
    manager = I2IManager(vessel_dir="/tmp/test-i2i")
    
    # Create test features
    test_features = {
        "frame": 123,
        "timestamp": time.time(),
        "raw_features": {
            "f0_hz": 440.0,
            "loudness": -20.0,
            "jitter": 0.01,
        },
        "midi_cc": {7: 80, 1: 60}
    }
    
    success = manager.publish_features(test_features)
    print(f"✅ Publish features {'succeeded' if success else 'failed'}")
    
    # Clean up
    import shutil
    shutil.rmtree("/tmp/test-i2i", ignore_errors=True)


if __name__ == "__main__":
    test_i2i_integration()
