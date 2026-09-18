"""
Task data model and storage.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from enum import Enum


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Task:
    id: int
    title: str
    description: str = ""
    done: bool = False
    priority: str = "medium"
    tags: List[str] = None
    due_date: Optional[str] = None
    created_at: str = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class TaskStore:
    """Manage task storage in JSON file."""

    def __init__(self, file_path: str = None):
        if file_path is None:
            home = Path.home()
            data_dir = home / ".todo-cli"
            data_dir.mkdir(exist_ok=True)
            file_path = str(data_dir / "tasks.json")
        self.file_path = Path(file_path)
        self.tasks: List[Task] = []
        self._load()

    def _load(self):
        """Load tasks from file."""
        if self.file_path.exists():
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            self.tasks = [Task(**t) for t in data]

    def _save(self):
        """Save tasks to file."""
        data = [asdict(t) for t in self.tasks]
        self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_task(self, title: str, description: str = "",
                 priority: str = "medium", tags: List[str] = None,
                 due_date: str = None) -> Task:
        """Add a new task."""
        task_id = max((t.id for t in self.tasks), default=0) + 1
        task = Task(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            tags=tags or [],
            due_date=due_date,
        )
        self.tasks.append(task)
        self._save()
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def list_tasks(self, include_done: bool = True,
                   priority: str = None,
                   tag: str = None) -> List[Task]:
        """List tasks with optional filters."""
        result = self.tasks

        if not include_done:
            result = [t for t in result if not t.done]

        if priority:
            result = [t for t in result if t.priority == priority]

        if tag:
            result = [t for t in result if tag in t.tags]

        return result

    def complete_task(self, task_id: int) -> Optional[Task]:
        """Mark a task as completed."""
        task = self.get_task(task_id)
        if task:
            task.done = True
            task.completed_at = datetime.now().isoformat()
            self._save()
        return task

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        task = self.get_task(task_id)
        if task:
            self.tasks.remove(task)
            self._save()
            return True
        return False

    def update_task(self, task_id: int, **kwargs) -> Optional[Task]:
        """Update a task's fields."""
        task = self.get_task(task_id)
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            self._save()
        return task

    def get_stats(self) -> Dict:
        """Get task statistics."""
        total = len(self.tasks)
        completed = len([t for t in self.tasks if t.done])
        pending = total - completed

        by_priority = {}
        for p in Priority:
            by_priority[p.value] = len([t for t in self.tasks if t.priority == p.value and not t.done])

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "by_priority": by_priority,
        }
