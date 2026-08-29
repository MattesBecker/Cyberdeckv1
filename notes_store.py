import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


FILENAME_PATTERN = re.compile(r"^\d{8}_\d{6}\.md$")
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
CREATED_FORMAT = "%Y-%m-%d %H:%M:%S"


class NotesStoreError(RuntimeError):
    """Raised when a note cannot be stored or deleted safely."""


@dataclass(frozen=True)
class Note:
    filename: str
    created: datetime
    title: str
    text: str


class NotesStore:
    """Store notes as small UTF-8 Markdown files in one directory."""

    def __init__(self, notes_dir: Path) -> None:
        self.notes_dir = Path(notes_dir)

    def ensure_directory(self) -> None:
        if self.notes_dir.is_symlink():
            raise NotesStoreError("Notes directory must not be a symbolic link.")
        try:
            self.notes_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise NotesStoreError(
                "Could not create notes directory: {0}".format(exc)
            ) from exc

    def list_notes(self) -> List[Note]:
        self.ensure_directory()
        try:
            paths = list(self.notes_dir.iterdir())
        except OSError as exc:
            raise NotesStoreError("Could not list notes: {0}".format(exc)) from exc

        notes = []
        for path in paths:
            if (
                path.is_symlink()
                or not path.is_file()
                or FILENAME_PATTERN.fullmatch(path.name) is None
            ):
                continue
            note = self._read_note(path)
            if note is not None:
                notes.append(note)

        # Timestamp filenames sort chronologically without extra filesystem reads.
        notes.sort(key=lambda note: note.filename, reverse=True)
        return notes

    def create_note(
        self,
        title: str,
        text: str,
        created: Optional[datetime] = None,
    ) -> Note:
        self.ensure_directory()
        clean_title = " ".join(title.splitlines()).strip() or "Untitled"
        clean_text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip()
        timestamp = (created or datetime.now()).replace(microsecond=0)

        # Avoid overwriting when two notes are created during the same second.
        for offset in range(86400):
            note_time = timestamp + timedelta(seconds=offset)
            filename = note_time.strftime(TIMESTAMP_FORMAT) + ".md"
            path = self.notes_dir / filename
            contents = self._serialize(note_time, clean_title, clean_text)
            try:
                with path.open("x", encoding="utf-8", newline="\n") as note_file:
                    note_file.write(contents)
            except FileExistsError:
                continue
            except OSError as exc:
                raise NotesStoreError(
                    "Could not save note '{0}': {1}".format(clean_title, exc)
                ) from exc
            return Note(filename, note_time, clean_title, clean_text)

        raise NotesStoreError("Could not find a free timestamp filename.")

    def delete_note(self, note: Note) -> None:
        self.ensure_directory()
        if FILENAME_PATTERN.fullmatch(note.filename) is None:
            raise NotesStoreError("Refusing to delete an invalid note filename.")

        path = self.notes_dir / note.filename
        if path.is_symlink():
            raise NotesStoreError("Refusing to delete a symbolic link.")
        try:
            path.unlink()
        except FileNotFoundError:
            raise NotesStoreError("The note no longer exists.")
        except OSError as exc:
            raise NotesStoreError("Could not delete note: {0}".format(exc)) from exc

    @staticmethod
    def _serialize(created: datetime, title: str, text: str) -> str:
        return (
            "---\n"
            "created: {0}\n"
            "title: {1}\n"
            "---\n\n"
            "{2}\n"
        ).format(created.strftime(CREATED_FORMAT), title, text)

    def _read_note(self, path: Path) -> Optional[Note]:
        try:
            contents = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None

        metadata = {}
        body_start = 0
        lines = contents.splitlines()
        if lines and lines[0].strip() == "---":
            for index, line in enumerate(lines[1:], start=1):
                separator = line.strip()
                if separator == "---" or (
                    len(separator) >= 3 and set(separator) == {"-"}
                ):
                    body_start = index + 1
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip().lower()] = value.strip()

        try:
            created = datetime.strptime(
                metadata.get("created", ""), CREATED_FORMAT
            )
        except ValueError:
            try:
                created = datetime.strptime(path.stem, TIMESTAMP_FORMAT)
            except ValueError:
                return None

        title = metadata.get("title", "").strip() or "Untitled"
        text = "\n".join(lines[body_start:]).strip()
        return Note(path.name, created, title, text)
