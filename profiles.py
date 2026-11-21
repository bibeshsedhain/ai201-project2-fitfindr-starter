"""Explicit local style memory; profiles survive process restarts."""
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path


def validate_profile(profile: dict) -> dict:
    if not isinstance(profile, dict):
        raise ValueError("Profile must be a JSON object.")
    wardrobe = profile.get("wardrobe", {"items": []})
    if not isinstance(wardrobe, dict) or not isinstance(wardrobe.get("items"), list):
        raise ValueError("Wardrobe must contain an items list.")
    for item in wardrobe["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("Each wardrobe item needs a name string.")
        for field in ("colors", "style_tags"):
            if not isinstance(item.get(field, []), list) or not all(
                isinstance(value, str) for value in item.get(field, [])
            ):
                raise ValueError(f"Each item's {field} must be a list of strings.")
    preferences = profile.get("style_preferences", "")
    size = profile.get("size")
    budget = profile.get("max_price")
    if not isinstance(preferences, str) or (size is not None and not isinstance(size, str)):
        raise ValueError("Style preferences and size must be text.")
    if budget is not None:
        if isinstance(budget, bool):
            raise ValueError("Budget must be a nonnegative number.")
        budget = float(budget)
        if not math.isfinite(budget) or budget < 0:
            raise ValueError("Budget must be a finite nonnegative number.")
    return {"version": 1, "wardrobe": wardrobe, "style_preferences": preferences,
            "size": size.strip() or None if size else None, "max_price": budget}


class ProfileStore:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory or os.environ.get(
            "FITFINDR_PROFILE_DIR", Path(__file__).parent / ".fitfindr" / "profiles"))

    def _path(self, profile_id: str) -> Path:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("Enter a profile name to save, load, or delete.")
        key = hashlib.sha256(profile_id.strip().encode()).hexdigest()
        return self.directory / f"{key}.json"

    def load(self, profile_id: str) -> dict | None:
        path = self._path(profile_id)
        if not path.exists():
            return None
        return validate_profile(json.loads(path.read_text(encoding="utf-8")))

    def save(self, profile_id: str, profile: dict) -> dict:
        path = self._path(profile_id)
        validated = validate_profile(profile)
        self.directory.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.directory, delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(validated, handle, indent=2)
            os.replace(temp_path, path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
        return validated

    def delete(self, profile_id: str) -> None:
        self._path(profile_id).unlink(missing_ok=True)
