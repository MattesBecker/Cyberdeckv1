import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional


TASK_ID_PATTERN = re.compile(r"^\d{8}_\d{6}$")
TASK_ID_FORMAT = "%Y%m%d_%H%M%S"
CREATED_FORMAT = "%Y-%m-%dT%H:%M:%S"
logger = logging.getLogger(__name__)


class TasksStoreError(RuntimeError):
    """Raised when task data cannot be read or changed safely."""


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    done: bool
    created: datetime


class TasksStore:
    """Store a small task list in one atomically replaced JSON file."""

    def __init__(self, tasks_file: Path) -> None:
        self.tasks_file = Path(tasks_file)

    def ensure_file(self) -> None:
        if self.tasks_file.is_symlink():
            raise TasksStoreError("Tasks file must not be a symbolic link.")
        try:
            self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise TasksStoreError(
                "Could not create tasks directory: {0}".format(exc)
            ) from exc

        if self.tasks_file.exists():
            if not self.tasks_file.is_file():
                raise TasksStoreError("Tasks path is not a regular file.")
            return
        self._atomic_write([])

    def list_tasks(self) -> List[Task]:
        tasks = self._load_tasks()
        tasks.sort(key=lambda task: task.created, reverse=True)
        tasks.sort(key=lambda task: task.done)
        return tasks

    def create_task(
        self, title: str, created: Optional[datetime] = None
    ) -> Task:
        clean_title = " ".join(title.splitlines()).strip()
        if not clean_title:
            raise TasksStoreError("Task title must not be empty.")

        tasks = self._load_tasks()
        existing_ids = {task.id for task in tasks}
        timestamp = (created or datetime.now()).replace(microsecond=0)
        for offset in range(86400):
            task_time = timestamp + timedelta(seconds=offset)
            task_id = task_time.strftime(TASK_ID_FORMAT)
            if task_id in existing_ids:
                continue
            task = Task(task_id, clean_title, False, task_time)
            self._atomic_write(tasks + [task])
            return task
        raise TasksStoreError("Could not create a unique timestamp task ID.")

    def get_task(self, task_id: str) -> Optional[Task]:
        if TASK_ID_PATTERN.fullmatch(task_id) is None:
            return None
        for task in self._load_tasks():
            if task.id == task_id:
                return task
        return None

    def toggle_task(self, task_id: str) -> Task:
        self._validate_task_id(task_id)
        tasks = self._load_tasks()
        updated = None
        changed_tasks = []
        for task in tasks:
            if task.id == task_id:
                updated = Task(task.id, task.title, not task.done, task.created)
                changed_tasks.append(updated)
            else:
                changed_tasks.append(task)
        if updated is None:
            raise TasksStoreError("The selected task no longer exists.")
        self._atomic_write(changed_tasks)
        return updated

    def delete_task(self, task_id: str) -> None:
        self._validate_task_id(task_id)
        tasks = self._load_tasks()
        remaining = [task for task in tasks if task.id != task_id]
        if len(remaining) == len(tasks):
            raise TasksStoreError("The selected task no longer exists.")
        self._atomic_write(remaining)

    def _load_tasks(self) -> List[Task]:
        self.ensure_file()
        try:
            raw_bytes = self.tasks_file.read_bytes()
        except OSError as exc:
            raise TasksStoreError("Could not read tasks: {0}".format(exc)) from exc

        if not raw_bytes.strip():
            return []
        try:
            raw_text = raw_bytes.decode("utf-8")
            data = json.loads(raw_text)
        except (UnicodeError, json.JSONDecodeError) as exc:
            backup = self._backup_corrupt_data(raw_bytes)
            raise TasksStoreError(
                "tasks.json is invalid; original data was preserved and "
                "backed up as {0}: {1}".format(backup.name, exc)
            ) from exc

        if not isinstance(data, list):
            backup = self._backup_corrupt_data(raw_bytes)
            raise TasksStoreError(
                "tasks.json must contain a JSON list; original data was "
                "preserved and backed up as {0}.".format(backup.name)
            )

        tasks = []
        seen_ids = set()
        for index, item in enumerate(data):
            task = self._parse_task(item)
            if task is None or task.id in seen_ids:
                logger.warning("Skipping invalid task entry at index %d", index)
                continue
            seen_ids.add(task.id)
            tasks.append(task)
        return tasks

    @staticmethod
    def _parse_task(item) -> Optional[Task]:
        if not isinstance(item, dict):
            return None
        task_id = item.get("id")
        title = item.get("title")
        done = item.get("done")
        created_value = item.get("created")
        if (
            not isinstance(task_id, str)
            or TASK_ID_PATTERN.fullmatch(task_id) is None
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(done, bool)
            or not isinstance(created_value, str)
        ):
            return None
        try:
            created = datetime.strptime(created_value, CREATED_FORMAT)
        except ValueError:
            return None
        clean_title = " ".join(title.splitlines()).strip()
        if not clean_title:
            return None
        return Task(task_id, clean_title, done, created)

    @staticmethod
    def _serialize_task(task: Task):
        return {
            "id": task.id,
            "title": task.title,
            "done": task.done,
            "created": task.created.strftime(CREATED_FORMAT),
        }

    def _atomic_write(self, tasks: List[Task]) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=".tasks.",
                suffix=".tmp",
                dir=str(self.tasks_file.parent),
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(
                    [self._serialize_task(task) for task in tasks],
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                )
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(str(temporary_path), str(self.tasks_file))
            temporary_path = None
        except OSError as exc:
            raise TasksStoreError(
                "Could not save tasks atomically: {0}".format(exc)
            ) from exc
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
                except OSError:
                    logger.warning(
                        "Could not remove temporary tasks file: %s",
                        temporary_path.name,
                    )

    def _backup_corrupt_data(self, raw_data: bytes) -> Path:
        timestamp = datetime.now().strftime(TASK_ID_FORMAT)
        for suffix in range(1000):
            extra = "" if suffix == 0 else "-{0}".format(suffix)
            backup = self.tasks_file.with_name(
                self.tasks_file.name + ".corrupt-" + timestamp + extra
            )
            try:
                with backup.open("xb") as backup_file:
                    backup_file.write(raw_data)
                return backup
            except FileExistsError:
                continue
            except OSError as exc:
                raise TasksStoreError(
                    "tasks.json is invalid and its backup could not be "
                    "created: {0}".format(exc)
                ) from exc
        raise TasksStoreError("Could not create a unique corrupt-data backup.")

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if (
            not isinstance(task_id, str)
            or TASK_ID_PATTERN.fullmatch(task_id) is None
        ):
            raise TasksStoreError("Invalid task ID.")
