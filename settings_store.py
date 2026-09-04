from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Dict

from config import (
    BOOT_SCREEN_SECONDS,
    DEFAULT_START_SCREEN,
    KIWIX_ENABLED,
    PARTIAL_REFRESH_LIMIT,
)
from json_store import JSONStoreError, load_json, save_json


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeSettings:
    boot_enabled: bool = True
    boot_duration: float = BOOT_SCREEN_SECONDS
    partial_refresh_max: int = PARTIAL_REFRESH_LIMIT
    start_screen: str = DEFAULT_START_SCREEN
    kiwix_enabled: bool = KIWIX_ENABLED
    dashboard_wifi: bool = True
    dashboard_tasks: bool = True
    dashboard_storage: bool = True


class SettingsStore:
    """Validated, atomically saved runtime settings."""

    _BOOL_FIELDS = (
        "boot_enabled",
        "kiwix_enabled",
        "dashboard_wifi",
        "dashboard_tasks",
        "dashboard_storage",
    )

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> RuntimeSettings:
        defaults = RuntimeSettings()
        raw = load_json(self.path, {})
        if not isinstance(raw, dict):
            return defaults
        values: Dict[str, Any] = asdict(defaults)
        for field in self._BOOL_FIELDS:
            if isinstance(raw.get(field), bool):
                values[field] = raw[field]
        duration = raw.get("boot_duration")
        if _is_number(duration) and 0.0 <= float(duration) <= 10.0:
            values["boot_duration"] = float(duration)
        partial = raw.get("partial_refresh_max")
        if isinstance(partial, int) and not isinstance(partial, bool) and 1 <= partial <= 50:
            values["partial_refresh_max"] = partial
        if raw.get("start_screen") in ("dashboard", "menu"):
            values["start_screen"] = raw["start_screen"]
        return RuntimeSettings(**values)

    def save(self, settings: RuntimeSettings) -> None:
        self._validate(settings)
        try:
            save_json(self.path, asdict(settings))
        except JSONStoreError as exc:
            raise SettingsError(str(exc)) from exc

    def update(self, settings: RuntimeSettings, **changes: Any) -> RuntimeSettings:
        try:
            updated = replace(settings, **changes)
        except TypeError as exc:
            raise SettingsError("Unknown setting.") from exc
        self._validate(updated)
        self.save(updated)
        return updated

    @classmethod
    def _validate(cls, settings: RuntimeSettings) -> None:
        for field in cls._BOOL_FIELDS:
            if not isinstance(getattr(settings, field), bool):
                raise SettingsError("Invalid setting: {0}".format(field))
        if not _is_number(settings.boot_duration) or not 0.0 <= float(settings.boot_duration) <= 10.0:
            raise SettingsError("Boot duration must be between 0 and 10 seconds.")
        if (
            not isinstance(settings.partial_refresh_max, int)
            or isinstance(settings.partial_refresh_max, bool)
            or not 1 <= settings.partial_refresh_max <= 50
        ):
            raise SettingsError("Partial refresh count must be between 1 and 50.")
        if settings.start_screen not in ("dashboard", "menu"):
            raise SettingsError("Start screen must be dashboard or menu.")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
