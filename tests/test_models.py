import pytest
from todo_cli.models import TaskStore, Task


def test_add_task(tmp_path):
    """Test adding a task."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    task = store.add_task("Test task", priority="high", tags=["work", "urgent"])
    assert task.id == 1
    assert task.title == "Test task"
    assert task.priority == "high"
    assert "work" in task.tags


def test_list_tasks(tmp_path):
    """Test listing tasks."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    store.add_task("Task 1")
    store.add_task("Task 2")
    store.add_task("Task 3", priority="high")

    all_tasks = store.list_tasks()
    assert len(all_tasks) == 3

    high_priority = store.list_tasks(priority="high")
    assert len(high_priority) == 1


def test_complete_task(tmp_path):
    """Test completing a task."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    task = store.add_task("Test task")

    completed = store.complete_task(task.id)
    assert completed.done is True
    assert completed.completed_at is not None


def test_delete_task(tmp_path):
    """Test deleting a task."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    task = store.add_task("Test task")

    assert store.delete_task(task.id) is True
    assert store.get_task(task.id) is None


def test_task_stats(tmp_path):
    """Test task statistics."""
    store = TaskStore(str(tmp_path / "tasks.json"))
    store.add_task("Task 1", priority="high")
    store.add_task("Task 2", priority="medium")
    task3 = store.add_task("Task 3", priority="low")
    store.complete_task(task3.id)

    stats = store.get_stats()
    assert stats["total"] == 3
    assert stats["completed"] == 1
    assert stats["pending"] == 2
