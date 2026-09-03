import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union


logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = frozenset((".md", ".txt"))


class LibraryServiceError(RuntimeError):
    """Raised when a library path or document cannot be accessed safely."""


@dataclass(frozen=True)
class LibraryEntry:
    name: str
    relative_path: Path
    is_directory: bool


@dataclass(frozen=True)
class LibraryDocument:
    name: str
    relative_path: Path
    text: str


class LibraryService:
    """List and read supported files below one trusted library directory."""

    def __init__(self, library_dir: Path) -> None:
        self.library_dir = Path(library_dir)

    def ensure_directory(self) -> None:
        if self.library_dir.is_symlink():
            raise LibraryServiceError(
                "Library directory must not be a symbolic link."
            )
        try:
            self.library_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LibraryServiceError(
                "Could not create library directory: {0}".format(exc)
            ) from exc
        if not self.library_dir.is_dir():
            raise LibraryServiceError("Library path is not a directory.")

    def list_directory(
        self, relative_path: Union[str, Path] = Path()
    ) -> List[LibraryEntry]:
        directory = self._safe_existing_path(relative_path)
        if not directory.is_dir():
            raise LibraryServiceError("Library item is not a directory.")

        requested_path = self._validate_relative_path(relative_path)
        try:
            children = list(directory.iterdir())
        except OSError as exc:
            raise LibraryServiceError(
                "Could not list library directory: {0}".format(exc)
            ) from exc

        entries = []
        for child in children:
            if child.is_symlink():
                logger.warning("Skipping library symbolic link: %s", child.name)
                continue
            try:
                is_directory = child.is_dir()
                is_supported_file = (
                    child.is_file()
                    and child.suffix.lower() in SUPPORTED_SUFFIXES
                )
            except OSError:
                logger.warning("Skipping inaccessible library item: %s", child.name)
                continue
            if not is_directory and not is_supported_file:
                continue
            entries.append(
                LibraryEntry(
                    name=child.name,
                    relative_path=requested_path / child.name,
                    is_directory=is_directory,
                )
            )

        entries.sort(
            key=lambda entry: (
                not entry.is_directory,
                entry.name.casefold(),
                entry.name,
            )
        )
        return entries

    def read_document(
        self, relative_path: Union[str, Path]
    ) -> LibraryDocument:
        requested_path = self._validate_relative_path(relative_path)
        path = self._safe_existing_path(requested_path)
        if not path.is_file():
            raise LibraryServiceError("Library item is not a regular file.")
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise LibraryServiceError("Unsupported library file type.")

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise LibraryServiceError("File is not valid UTF-8.") from exc
        except OSError as exc:
            raise LibraryServiceError(
                "Could not read library file: {0}".format(exc)
            ) from exc

        return LibraryDocument(path.name, requested_path, text)

    def _safe_existing_path(self, relative_path: Union[str, Path]) -> Path:
        self.ensure_directory()
        requested_path = self._validate_relative_path(relative_path)
        candidate = self.library_dir / requested_path

        current = self.library_dir
        for part in requested_path.parts:
            current = current / part
            if current.is_symlink():
                raise LibraryServiceError(
                    "Symbolic links are not allowed in the library."
                )

        try:
            root = self.library_dir.resolve(strict=True)
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise LibraryServiceError(
                "Library item is unavailable: {0}".format(exc)
            ) from exc

        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise LibraryServiceError(
                "Refusing to access a path outside the library."
            ) from exc
        return resolved

    @staticmethod
    def _validate_relative_path(relative_path: Union[str, Path]) -> Path:
        try:
            path = Path(relative_path)
        except (TypeError, ValueError) as exc:
            raise LibraryServiceError("Invalid library path.") from exc
        if "\x00" in str(path):
            raise LibraryServiceError("Invalid library path.")
        if path.is_absolute() or ".." in path.parts:
            raise LibraryServiceError(
                "Refusing to access a path outside the library."
            )
        return path
