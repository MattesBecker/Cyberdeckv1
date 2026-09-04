import logging
from pathlib import Path
from typing import List

from .base import (
    ITEM_TYPE_DIRECTORY,
    ITEM_TYPE_DOCUMENT,
    LibraryDocument,
    LibraryItem,
    LibraryProvider,
    LibraryProviderError,
)


logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = frozenset((".md", ".txt"))


class LocalLibraryProvider(LibraryProvider):
    """Browse UTF-8 text files below one trusted local directory."""

    key = "local"
    title = "Local files"

    def __init__(self, library_dir: Path) -> None:
        self.library_dir = Path(library_dir)

    def ensure_directory(self) -> None:
        if self.library_dir.is_symlink():
            raise LibraryProviderError(
                "Library directory must not be a symbolic link."
            )
        try:
            self.library_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LibraryProviderError(
                "Could not create library directory: {0}".format(exc)
            ) from exc
        if not self.library_dir.is_dir():
            raise LibraryProviderError("Library path is not a directory.")

    def list_items(self, container_id: str = "") -> List[LibraryItem]:
        directory = self._safe_existing_path(container_id)
        if not directory.is_dir():
            raise LibraryProviderError("Library item is not a directory.")

        relative_path = self._validate_id(container_id)
        try:
            children = list(directory.iterdir())
        except OSError as exc:
            raise LibraryProviderError(
                "Could not list library directory: {0}".format(exc)
            ) from exc

        items = []
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

            child_path = relative_path / child.name
            items.append(
                LibraryItem(
                    provider=self.key,
                    id=self._path_to_id(child_path),
                    title=child.name,
                    item_type=(
                        ITEM_TYPE_DIRECTORY
                        if is_directory
                        else ITEM_TYPE_DOCUMENT
                    ),
                )
            )

        items.sort(
            key=lambda item: (
                item.item_type != ITEM_TYPE_DIRECTORY,
                item.title.casefold(),
                item.title,
            )
        )
        return items

    def open_item(self, item_id: str) -> LibraryDocument:
        relative_path = self._validate_id(item_id)
        path = self._safe_existing_path(item_id)
        if not path.is_file():
            raise LibraryProviderError("Library item is not a regular file.")
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise LibraryProviderError("Unsupported library file type.")

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise LibraryProviderError("File is not valid UTF-8.") from exc
        except OSError as exc:
            raise LibraryProviderError(
                "Could not read library file: {0}".format(exc)
            ) from exc

        normalized_id = self._path_to_id(relative_path)
        return LibraryDocument(
            provider=self.key,
            id=normalized_id,
            title=path.name,
            text=text,
            source=normalized_id,
        )

    def get_title(self, item_id: str) -> str:
        if not item_id:
            return self.title
        return self._safe_existing_path(item_id).name

    def _safe_existing_path(self, item_id: str) -> Path:
        self.ensure_directory()
        relative_path = self._validate_id(item_id)
        candidate = self.library_dir / relative_path

        current = self.library_dir
        for part in relative_path.parts:
            current = current / part
            if current.is_symlink():
                raise LibraryProviderError(
                    "Symbolic links are not allowed in the library."
                )

        try:
            root = self.library_dir.resolve(strict=True)
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise LibraryProviderError(
                "Library item is unavailable: {0}".format(exc)
            ) from exc

        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise LibraryProviderError(
                "Refusing to access a path outside the library."
            ) from exc
        return resolved

    @staticmethod
    def _validate_id(item_id: str) -> Path:
        if not isinstance(item_id, str) or "\x00" in item_id:
            raise LibraryProviderError("Invalid local library item ID.")
        try:
            path = Path(item_id)
        except (TypeError, ValueError) as exc:
            raise LibraryProviderError(
                "Invalid local library item ID."
            ) from exc
        if path.is_absolute() or ".." in path.parts:
            raise LibraryProviderError(
                "Refusing to access a path outside the library."
            )
        return path

    @staticmethod
    def _path_to_id(path: Path) -> str:
        return "" if not path.parts else path.as_posix()
