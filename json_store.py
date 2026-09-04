import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


class JSONStoreError(RuntimeError):
    """Raised when a small runtime JSON file cannot be saved safely."""


def load_json(path: Path, default: Any) -> Any:
    """Load JSON, returning a fresh default for missing or damaged data."""
    path = Path(path)
    if path.is_symlink():
        logger.warning("Ignoring symbolic-link JSON store: %s", path)
        return _copy_default(default)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _copy_default(default)
    except (OSError, UnicodeError) as exc:
        logger.warning("Could not read JSON store %s: %s", path, exc)
        return _copy_default(default)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Ignoring damaged JSON store %s: %s", path, exc)
        return _copy_default(default)


def save_json(path: Path, value: Any) -> None:
    """Atomically replace one UTF-8 JSON file in its configured directory."""
    path = Path(path)
    if path.is_symlink():
        raise JSONStoreError("JSON store must not be a symbolic link.")
    temporary_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=".{0}.".format(path.stem),
            suffix=".tmp",
            dir=str(path.parent),
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(str(temporary_path), str(path))
        temporary_path = None
    except (OSError, TypeError, ValueError) as exc:
        raise JSONStoreError("Could not save {0}: {1}".format(path.name, exc)) from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass


def _copy_default(default: Any) -> Any:
    if isinstance(default, dict):
        return dict(default)
    if isinstance(default, list):
        return list(default)
    return default
