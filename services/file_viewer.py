from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


SUPPORTED_SUFFIXES = frozenset(
    (".txt", ".md", ".log", ".json", ".conf", ".ini", ".py", ".sh")
)


class FileViewerError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileEntry:
    path: Path
    title: str
    is_directory: bool


@dataclass(frozen=True)
class TextFile:
    path: Path
    title: str
    text: str
    truncated: bool


class FileViewerService:
    """Read bounded UTF-8 files below explicit roots only."""

    def __init__(self, roots: Sequence[Path], max_bytes: int) -> None:
        self.roots = tuple(Path(root).resolve() for root in roots)
        self.max_bytes = max(1024, int(max_bytes))

    def available_roots(self) -> List[FileEntry]:
        result = []
        for root in self.roots:
            try:
                if root.is_dir() and not root.is_symlink():
                    result.append(FileEntry(root, str(root), True))
            except OSError:
                continue
        return result

    def list_directory(self, directory: Path) -> List[FileEntry]:
        safe_directory = self._safe_path(directory)
        if not safe_directory.is_dir():
            raise FileViewerError("Folder unavailable")
        entries = []
        try:
            children = list(safe_directory.iterdir())
        except OSError as exc:
            raise FileViewerError("Folder not readable") from exc
        for child in children:
            try:
                if child.is_symlink():
                    continue
                if child.is_dir():
                    entries.append(FileEntry(child, child.name + "/", True))
                elif child.is_file() and child.suffix.lower() in SUPPORTED_SUFFIXES:
                    entries.append(FileEntry(child, child.name, False))
            except OSError:
                continue
        entries.sort(key=lambda entry: (not entry.is_directory, entry.title.lower()))
        return entries

    def open_text(self, path: Path) -> TextFile:
        raw_path = Path(path)
        if raw_path.is_symlink():
            raise FileViewerError("Symbolic links are not allowed")
        safe_path = self._safe_path(raw_path)
        if safe_path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise FileViewerError("Unsupported file type")
        try:
            if not safe_path.is_file():
                raise FileViewerError("File unavailable")
            with safe_path.open("rb") as handle:
                data = handle.read(self.max_bytes + 1)
        except FileViewerError:
            raise
        except OSError as exc:
            raise FileViewerError("File not readable") from exc
        truncated = len(data) > self.max_bytes
        data = data[: self.max_bytes]
        if b"\x00" in data:
            raise FileViewerError("Binary files are not supported")
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileViewerError("File is not valid UTF-8") from exc
        if truncated:
            text += "\n\n[truncated at {0} bytes]".format(self.max_bytes)
        return TextFile(safe_path, safe_path.name, text, truncated)

    def root_for(self, path: Path) -> Path:
        safe = self._safe_path(path)
        for root in self.roots:
            if safe == root or root in safe.parents:
                return root
        raise FileViewerError("Path outside allowed roots")

    def _safe_path(self, path: Path) -> Path:
        try:
            resolved = Path(path).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise FileViewerError("Invalid path") from exc
        for root in self.roots:
            if resolved == root or root in resolved.parents:
                return resolved
        raise FileViewerError("Path outside allowed roots")
