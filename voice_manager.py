#!/usr/bin/env python3
"""
Voice Manager for FlowSmartly
Handles user voice profiles and cloning
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

class VoiceManager:
    """Manage user voice profiles"""

    def __init__(self, storage_dir: str = "/workspace/voices"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_file = self.storage_dir / "profiles.json"

        # Load profiles
        self.profiles = self._load_profiles()

    def _load_profiles(self) -> Dict:
        """Load voice profiles from disk"""
        if self.profiles_file.exists():
            with open(self.profiles_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_profiles(self):
        """Save voice profiles to disk"""
        with open(self.profiles_file, 'w') as f:
            json.dump(self.profiles, f, indent=2)

    def create_profile(
        self,
        user_id: str,
        profile_name: str,
        voice_sample_url: str,
        transcript: str,
        language: str = "en",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a new voice profile

        Args:
            user_id: User ID
            profile_name: Name for this voice
            voice_sample_url: URL to voice sample audio
            transcript: Text transcript of the voice sample
            language: Language code
            metadata: Optional metadata

        Returns:
            Voice profile dictionary
        """
        profile_id = f"{user_id}_{profile_name}_{len(self.profiles)}"

        profile = {
            "id": profile_id,
            "user_id": user_id,
            "name": profile_name,
            "voice_sample_url": voice_sample_url,
            "transcript": transcript,
            "language": language,
            "metadata": metadata or {},
            "created_at": str(Path.ctime(self.profiles_file))
        }

        self.profiles[profile_id] = profile
        self._save_profiles()

        return profile

    def get_profile(self, profile_id: str) -> Optional[Dict]:
        """Get a voice profile by ID"""
        return self.profiles.get(profile_id)

    def get_user_profiles(self, user_id: str) -> List[Dict]:
        """Get all voice profiles for a user"""
        return [
            profile for profile in self.profiles.values()
            if profile.get("user_id") == user_id
        ]

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a voice profile"""
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            self._save_profiles()
            return True
        return False

    def update_profile(self, profile_id: str, updates: Dict) -> Optional[Dict]:
        """Update a voice profile"""
        if profile_id in self.profiles:
            self.profiles[profile_id].update(updates)
            self._save_profiles()
            return self.profiles[profile_id]
        return None


# Example usage
if __name__ == "__main__":
    manager = VoiceManager()

    # Create a test profile
    profile = manager.create_profile(
        user_id="user123",
        profile_name="My Voice",
        voice_sample_url="https://example.com/voice.wav",
        transcript="This is my voice sample for cloning",
        language="en",
        metadata={"quality": "high", "duration_sec": 15}
    )

    print("Created profile:", json.dumps(profile, indent=2))

    # Get user profiles
    user_profiles = manager.get_user_profiles("user123")
    print(f"\nUser has {len(user_profiles)} voice profiles")
