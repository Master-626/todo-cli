"""Task data model and atomic, process-safe JSON storage."""

import copy
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class StorageError(Exception):
    """The task store could not be safely read or written."""


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


def _validate_tasks(tasks):
    seen = set()
    for task in tasks:
        if type(task.id) is not int or task.id < 1 or task.id in seen:
            raise ValueError("Task IDs must be unique positive integers")
        seen.add(task.id)
        if not isinstance(task.title, str) or not task.title.strip():
            raise ValueError("Task title must be a nonempty string")
        if not isinstance(task.description, str) or type(task.done) is not bool:
            raise ValueError("Task description must be text and done must be a boolean")
        if not isinstance(task.priority, str) or task.priority not in {p.value for p in Priority}:
            raise ValueError("Unknown task priority")
        if not isinstance(task.tags, list) or not all(isinstance(t, str) for t in task.tags):
            raise ValueError("Task tags must be a list of strings")
        for key in ("due_date", "created_at", "completed_at"):
            value = getattr(task, key)
            if value is not None and not isinstance(value, str):
                raise ValueError("Task {} must be text or null".format(key))


def _check_regular(path):
    """Reject aliases and nonregular files instead of replacing or following them."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise StorageError("Refusing linked or nonregular file: {}".format(path))
    return info


def _open_regular(path, flags):
    _check_regular(path)
    fd = os.open(str(path), flags | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0), 0o600)
    try:
        info = os.fstat(fd)
        current = _check_regular(path)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or current is None
                or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)):
            raise StorageError("Task file changed while opening: {}".format(path))
        return fd
    except BaseException:
        os.close(fd)
        raise


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field: {}".format(key))
        result[key] = value
    return result


class TaskStore:
    """Manage JSON tasks. All mutations reload under a separate process lock."""

    def __init__(self, file_path: str = None):
        path = Path(file_path) if file_path is not None else Path.home() / ".todo-cli" / "tasks.json"
        # Canonicalize directory aliases so cooperating writers share one lock.
        self.file_path = path.parent.resolve() / path.name
        self.lock_path = self.file_path.with_name(self.file_path.name + ".lock")
        self.tasks: List[Task] = []
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise StorageError("Cannot create task directory: {}".format(exc)) from exc
        with self._locked():
            self._load()

    def _load(self):
        try:
            try:
                fd = _open_regular(self.file_path, os.O_RDONLY)
            except FileNotFoundError:
                self.tasks = []
                return
            with os.fdopen(fd, "r", encoding="utf-8") as handle:
                data = json.load(handle, object_pairs_hook=_unique_object)
            if not isinstance(data, list) or not all(isinstance(t, dict) for t in data):
                raise ValueError("Expected a JSON array of task objects")
            tasks = [Task(**t) for t in data]
            _validate_tasks(tasks)
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            raise StorageError("Cannot read tasks from {}: {}".format(self.file_path, exc)) from exc
        self.tasks = tasks

    @contextmanager
    def _locked(self):
        """Keep the sidecar inode stable; never unlink a lock after releasing it."""
        handle = None
        acquired = False
        try:
            handle = os.fdopen(_open_regular(self.lock_path, os.O_RDWR | os.O_CREAT), "r+b")
            if os.name == "nt":
                import msvcrt

                if os.fstat(handle.fileno()).st_size == 0:
                    handle.write(b"\0")
                    handle.flush()

                def acquire():
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

                def release():
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif os.name == "posix":
                import fcntl

                def acquire():
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                def release():
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            else:
                raise StorageError("Process locking is unsupported on this platform")
            deadline = time.monotonic() + 10
            while True:
                try:
                    acquire()
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise StorageError("Cannot acquire task lock: {}".format(self.lock_path))
                    time.sleep(0.05)
            yield
        except OSError as exc:
            raise StorageError("Task storage operation failed: {}".format(exc)) from exc
        finally:
            if handle is not None:
                try:
                    if acquired:
                        release()
                finally:
                    handle.close()

    def _save(self):
        """Write fully and fsync before replacing; caller must hold the lock."""
        _validate_tasks(self.tasks)
        payload = json.dumps([asdict(t) for t in self.tasks], indent=2, ensure_ascii=False)
        temporary = None
        try:
            _check_regular(self.file_path)
            fd, temporary = tempfile.mkstemp(prefix=".tasks-", suffix=".tmp", dir=str(self.file_path.parent))
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            _check_regular(self.file_path)
            os.replace(temporary, self.file_path)
            temporary = None
        except (OSError, UnicodeError) as exc:
            raise StorageError("Cannot save tasks to {}: {}".format(self.file_path, exc)) from exc
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass

    @contextmanager
    def _transaction(self):
        with self._locked():
            self._load()
            previous = copy.deepcopy(self.tasks)
            try:
                yield
                _validate_tasks(self.tasks)
                if self.tasks != previous:
                    self._save()
            except BaseException:
                self.tasks = previous
                raise

    def add_task(self, title: str, description: str = "", priority: str = "medium",
                 tags: List[str] = None, due_date: str = None) -> Task:
        with self._transaction():
            task = Task(id=max((t.id for t in self.tasks), default=0) + 1,
                        title=title, description=description, priority=priority,
                        tags=copy.deepcopy(tags), due_date=due_date)
            self.tasks.append(task)
            return copy.deepcopy(task)

    def _find(self, task_id):
        return next((t for t in self.tasks if t.id == task_id), None)

    def get_task(self, task_id: int) -> Optional[Task]:
        with self._locked():
            self._load()
            return copy.deepcopy(self._find(task_id))

    def list_tasks(self, include_done: bool = True, priority: str = None,
                   tag: str = None) -> List[Task]:
        with self._locked():
            self._load()
            return copy.deepcopy([t for t in self.tasks
                                  if (include_done or not t.done)
                                  and (not priority or t.priority == priority)
                                  and (not tag or tag in t.tags)])

    def complete_task(self, task_id: int) -> Optional[Task]:
        with self._transaction():
            task = self._find(task_id)
            if task is not None and not task.done:
                task.done = True
                task.completed_at = datetime.now().isoformat()
            return copy.deepcopy(task)

    def delete_task(self, task_id: int) -> bool:
        with self._transaction():
            task = self._find(task_id)
            if task is None:
                return False
            self.tasks.remove(task)
            return True

    def update_task(self, task_id: int, **kwargs) -> Optional[Task]:
        allowed = {field.name for field in fields(Task)} - {"id"}
        if not set(kwargs).issubset(allowed):
            raise ValueError("Unknown or immutable task field")
        with self._transaction():
            task = self._find(task_id)
            if task is not None:
                for key, value in kwargs.items():
                    setattr(task, key, copy.deepcopy(value))
            return copy.deepcopy(task)

    def get_stats(self) -> Dict:
        with self._locked():
            self._load()
            tasks = copy.deepcopy(self.tasks)
        completed = sum(t.done for t in tasks)
        return {
            "total": len(tasks),
            "completed": completed,
            "pending": len(tasks) - completed,
            "by_priority": {p.value: sum(t.priority == p.value and not t.done for t in tasks)
                            for p in Priority},
        }
