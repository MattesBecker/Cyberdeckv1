from typing import TYPE_CHECKING, List, Optional

from tasks_store import Task, TasksStore

from .base import BasePage

if TYPE_CHECKING:
    from display import EpaperDisplay


class TasksPage(BasePage):
    key = "tasks"
    title = "TASKS"

    def __init__(self, store: TasksStore) -> None:
        self.store = store
        self.tasks: List[Task] = []
        self.selected_index = 0
        self.list_offset = 0
        self._row_count = 5

    @property
    def selected_task(self) -> Optional[Task]:
        if self.selected_index == 0:
            return None
        task_index = self.selected_index - 1
        if task_index >= len(self.tasks):
            return None
        return self.tasks[task_index]

    def open_list(self, reset_selection: bool = True) -> None:
        self.reload()
        if reset_selection:
            self.selected_index = 0
            self.list_offset = 0

    def reload(self, preferred_id: Optional[str] = None) -> None:
        old_index = self.selected_index
        self.tasks = self.store.list_tasks()
        if preferred_id:
            for index, task in enumerate(self.tasks):
                if task.id == preferred_id:
                    self.selected_index = index + 1
                    break
            else:
                self.selected_index = min(old_index, len(self.tasks))
        else:
            self.selected_index = min(old_index, len(self.tasks))
        self._keep_selection_visible()

    def move_up(self) -> bool:
        item_count = len(self.tasks) + 1
        if item_count == 1:
            return False
        self.selected_index = (self.selected_index - 1) % item_count
        return True

    def move_down(self) -> bool:
        item_count = len(self.tasks) + 1
        if item_count == 1:
            return False
        self.selected_index = (self.selected_index + 1) % item_count
        return True

    def select(self) -> str:
        task = self.selected_task
        if task is None:
            return "new"
        updated = self.store.toggle_task(task.id)
        self.reload(preferred_id=updated.id)
        return "changed"

    def add_task(self, title: str) -> None:
        task = self.store.create_task(title)
        self.reload(preferred_id=task.id)

    def delete_selected_task(self) -> bool:
        task = self.selected_task
        if task is None:
            return False
        old_index = self.selected_index
        self.store.delete_task(task.id)
        self.tasks = self.store.list_tasks()
        self.selected_index = min(old_index, len(self.tasks))
        self._keep_selection_visible()
        return True

    def render(self, display: "EpaperDisplay") -> bool:
        self._row_count = display.body_line_count
        self._keep_selection_visible()
        labels = ["+ New task"] + [
            "[{0}] {1}".format("x" if task.done else " ", task.title)
            for task in self.tasks
        ]
        end = min(self.list_offset + self._row_count, len(labels))
        lines = []
        for index in range(self.list_offset, end):
            prefix = "> " if index == self.selected_index else "  "
            lines.append(prefix + labels[index])
        footer = "{0}/{1}  w/s  Enter  d  b".format(
            self.selected_index + 1, len(labels)
        )
        return display.render_page(self.title, lines, footer)

    def _keep_selection_visible(self) -> None:
        if self.selected_index < self.list_offset:
            self.list_offset = self.selected_index
        elif self.selected_index >= self.list_offset + self._row_count:
            self.list_offset = self.selected_index - self._row_count + 1
        maximum = max(0, len(self.tasks) + 1 - self._row_count)
        self.list_offset = min(self.list_offset, maximum)
