from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.command_palette import load_ui_config, save_ui_config


SETTINGS_PROFILES_KEY = "settings_profiles"
ACTIVE_SETTINGS_PROFILE_KEY = "active_settings_profile"


@dataclass(frozen=True)
class ProfilesSnapshot:
    profiles: dict[str, dict[str, Any]]
    active: str | None


def _normalize_name(name: str) -> str:
    return (name or "").strip()


def load_profiles_snapshot() -> ProfilesSnapshot:
    config = load_ui_config()
    raw_profiles = config.get(SETTINGS_PROFILES_KEY) or {}

    profiles: dict[str, dict[str, Any]] = {}
    if isinstance(raw_profiles, dict):
        for k, v in raw_profiles.items():
            if not isinstance(v, dict):
                continue
            name = _normalize_name(str(k))
            if not name:
                continue
            profiles[name] = dict(v)

    raw_active = config.get(ACTIVE_SETTINGS_PROFILE_KEY)
    active = _normalize_name(str(raw_active)) if raw_active else ""
    return ProfilesSnapshot(profiles=profiles, active=active or None)


def save_profiles_snapshot(snapshot: ProfilesSnapshot) -> None:
    config = load_ui_config()
    config[SETTINGS_PROFILES_KEY] = snapshot.profiles
    config[ACTIVE_SETTINGS_PROFILE_KEY] = snapshot.active
    save_ui_config(config)


def list_profile_names() -> list[str]:
    snap = load_profiles_snapshot()
    return sorted(snap.profiles.keys(), key=lambda s: s.lower())


def get_profile(name: str) -> dict[str, Any] | None:
    snap = load_profiles_snapshot()
    cleaned = _normalize_name(name)
    if not cleaned:
        return None
    profile = snap.profiles.get(cleaned)
    return dict(profile) if profile else None


def delete_profile(name: str) -> bool:
    cleaned = _normalize_name(name)
    if not cleaned:
        return False
    snap = load_profiles_snapshot()
    if cleaned not in snap.profiles:
        return False
    snap.profiles.pop(cleaned, None)
    active = snap.active
    if active == cleaned:
        active = None
    save_profiles_snapshot(ProfilesSnapshot(profiles=snap.profiles, active=active))
    return True


def rename_profile(old: str, new: str) -> bool:
    old_name = _normalize_name(old)
    new_name = _normalize_name(new)
    if not old_name or not new_name:
        return False
    snap = load_profiles_snapshot()
    if old_name not in snap.profiles:
        return False
    if new_name in snap.profiles:
        return False
    snap.profiles[new_name] = snap.profiles.pop(old_name)
    active = snap.active
    if active == old_name:
        active = new_name
    save_profiles_snapshot(ProfilesSnapshot(profiles=snap.profiles, active=active))
    return True


def set_active_profile(name: str | None) -> None:
    snap = load_profiles_snapshot()
    cleaned = _normalize_name(name or "")
    if cleaned and cleaned not in snap.profiles:
        raise KeyError(f"Profile not found: {cleaned}")
    save_profiles_snapshot(ProfilesSnapshot(profiles=snap.profiles, active=cleaned or None))


def snapshot_current_settings_as_profile(name: str, keys: list[str]) -> None:
    """Save the current UI config settings as a named profile.

    This snapshots values from the UI config file itself (i.e., last-saved UI state).
    """

    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Profile name is required")

    config = load_ui_config()
    payload: dict[str, Any] = {}
    for key in keys:
        if key in config:
            payload[key] = config.get(key)

    snap = load_profiles_snapshot()
    profiles = dict(snap.profiles)
    profiles[cleaned] = payload
    save_profiles_snapshot(ProfilesSnapshot(profiles=profiles, active=cleaned))


def upsert_profile(name: str, payload: dict[str, Any], *, set_active: bool = True) -> None:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Profile name is required")
    snap = load_profiles_snapshot()
    profiles = dict(snap.profiles)
    profiles[cleaned] = dict(payload)
    active = cleaned if set_active else snap.active
    save_profiles_snapshot(ProfilesSnapshot(profiles=profiles, active=active))


def duplicate_active_profile(new_name: str) -> None:
    snap = load_profiles_snapshot()
    if not snap.active:
        raise ValueError("No active profile to duplicate")
    active_payload = snap.profiles.get(snap.active)
    if not active_payload:
        raise ValueError("Active profile payload not found")
    upsert_profile(new_name, dict(active_payload), set_active=True)
