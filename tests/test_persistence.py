"""Regression and failure-injection tests use only disposable task stores."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from todo_cli import models
from todo_cli.models import StorageError, TaskStore


@pytest.fixture
def store(tmp_path):
    return TaskStore(str(tmp_path / "tasks.json"))


def test_import_annotations():
    from typing import get_type_hints
    assert get_type_hints(TaskStore.get_stats)["return"]


def test_stale_stores_reload_on_mutation_and_reads(tmp_path):
    path = str(tmp_path / "tasks.json")
    first, second = TaskStore(path), TaskStore(path)
    a = first.add_task("A")
    b = second.add_task("B")
    assert (a.id, b.id) == (1, 2)
    first.complete_task(a.id)
    second.update_task(b.id, title="Changed")
    assert second.get_task(a.id).done
    assert first.get_task(b.id).title == "Changed"
    assert first.get_stats()["total"] == 2
    first.delete_task(a.id)
    second.add_task("C")
    assert [t.title for t in first.list_tasks()] == ["Changed", "C"]


def test_results_do_not_alias_cached_tasks(store):
    tags = ["tag"]
    task = store.add_task("Original", tags=tags)
    task.title = "changed"
    tags.append("external")
    store.list_tasks()[0].tags.append("external")
    store.get_task(task.id).done = True
    assert store.get_task(task.id).title == "Original"
    assert store.get_task(task.id).tags == ["tag"]
    assert not store.get_task(task.id).done


@pytest.mark.parametrize("raw", [
    b"{", b"", b"null", b"{}", b"[null]", b"[{}]", b"\xff",
    b'[{"id":true,"title":"bad"}]',
    b'[{"id":1,"title":"a"},{"id":1,"title":"b"}]',
    b'[{"id":1,"title":"a","priority":[]}]',
    b'[{"id":1,"title":"a","tags":"oops"}]',
    b'[{"id":1,"title":"a","unknown":1}]',
])
def test_corrupt_existing_data_is_never_overwritten(tmp_path, raw):
    path = tmp_path / "tasks.json"
    store = TaskStore(str(path))
    path.write_bytes(raw)
    with pytest.raises(StorageError):
        store.add_task("Must not replace data")
    with pytest.raises(StorageError):
        TaskStore(str(path))
    assert path.read_bytes() == raw


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"title": None}, {"description": 4}, {"priority": []},
    {"priority": "unknown"}, {"tags": "text"}, {"tags": [1]},
    {"done": 1}, {"due_date": 42}, {"id": 999}, {"__dict__": {}}, {"unknown": 1},
])
def test_invalid_update_preserves_file_and_cache(store, changes):
    task = store.add_task("Keep")
    before = store.file_path.read_bytes()
    with pytest.raises(ValueError):
        store.update_task(task.id, **changes)
    assert store.file_path.read_bytes() == before
    assert store.tasks[0].title == "Keep"
    assert store.tasks[0].id == task.id


@pytest.mark.parametrize("failure", ["replace", "fsync", "mkstemp"])
def test_failed_save_preserves_original_and_cleans_temp(store, monkeypatch, failure):
    store.add_task("Keep")
    before = store.file_path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("Injected failure")

    target = models.tempfile if failure == "mkstemp" else models.os
    monkeypatch.setattr(target, failure, fail)
    with pytest.raises(StorageError, match="Injected failure"):
        store.add_task("Not saved")
    assert store.file_path.read_bytes() == before
    assert [t.title for t in store.tasks] == ["Keep"]
    assert not list(store.file_path.parent.glob(".tasks-*.tmp"))


def test_unicode_write_failure_preserves_data(store):
    store.add_task("Keep")
    before = store.file_path.read_bytes()
    with pytest.raises(StorageError):
        store.add_task("\ud800")
    assert store.file_path.read_bytes() == before
    assert not list(store.file_path.parent.glob(".tasks-*.tmp"))


def test_legacy_optional_fields_and_unicode(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text('[{"id":1,"title":"旧任务"}]', encoding="utf-8")
    store = TaskStore(str(path))
    assert store.get_task(1).tags == []
    store.add_task("新任务", tags=["工作"])
    assert TaskStore(str(path)).get_task(2).title == "新任务"


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "directory"])
@pytest.mark.parametrize("which", ["data", "lock"])
def test_reject_linked_and_nonregular_files(tmp_path, kind, which):
    path = tmp_path / "tasks.json"
    target = tmp_path / "target.json"
    target.write_text("[]")
    alias = path if which == "data" else tmp_path / "tasks.json.lock"
    try:
        if kind == "symlink":
            alias.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, alias)
        else:
            alias.mkdir()
    except (OSError, NotImplementedError) as exc:
        pytest.skip(str(exc))
    with pytest.raises(StorageError):
        TaskStore(str(path))
    assert target.read_text() == "[]"


def test_dangling_symlink_rejected(tmp_path):
    path = tmp_path / "tasks.json"
    try:
        path.symlink_to(tmp_path / "missing")
    except (OSError, NotImplementedError) as exc:
        pytest.skip(str(exc))
    with pytest.raises(StorageError):
        TaskStore(str(path))
    assert path.is_symlink()
    assert not (tmp_path / "missing").exists()


def test_parent_aliases_share_lock(tmp_path):
    parent = tmp_path / "data"
    parent.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(parent, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(str(exc))
    a, b = TaskStore(str(parent / "tasks.json")), TaskStore(str(alias / "tasks.json"))
    assert a.lock_path == b.lock_path
    a.add_task("A")
    b.add_task("B")
    assert a.get_stats()["total"] == 2


def child_env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(models.__file__).resolve().parents[1])
    return env


def wait_for_files(paths, processes, timeout=20):
    deadline = time.monotonic() + timeout
    while not all(p.exists() for p in paths):
        assert all(p.poll() is None for p in processes), "Worker exited before barrier"
        assert time.monotonic() < deadline, "Worker barrier timed out"
        time.sleep(0.02)


def test_simultaneous_process_writes_do_not_lose_tasks(tmp_path):
    code = '''
import sys, time
from pathlib import Path
from todo_cli.models import TaskStore
root, worker = Path(sys.argv[1]), sys.argv[2]
store = TaskStore(str(root / "tasks.json"))
(root / ("ready-" + worker)).touch()
while not (root / "go").exists(): time.sleep(0.01)
for i in range(12):
    task = store.add_task(worker + ":" + str(i))
    store.complete_task(task.id)
    store.update_task(task.id, tags=[worker])
'''
    workers = [subprocess.Popen([sys.executable, "-c", code, str(tmp_path), str(i)],
                                env=child_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
               for i in range(6)]
    try:
        wait_for_files([tmp_path / ("ready-" + str(i)) for i in range(6)], workers)
        (tmp_path / "go").touch()
        for worker in workers:
            out, err = worker.communicate(timeout=45)
            assert worker.returncode == 0, (out, err)
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.kill()
                worker.wait()
    tasks = TaskStore(str(tmp_path / "tasks.json")).list_tasks()
    assert len(tasks) == 72
    assert len({t.id for t in tasks}) == 72
    assert len({t.title for t in tasks}) == 72
    assert all(t.done and t.tags == [t.title.split(":")[0]] for t in tasks)


def test_killed_writer_leaves_valid_original_and_releases_lock(tmp_path):
    path = tmp_path / "tasks.json"
    TaskStore(str(path)).add_task("Keep")
    before = path.read_bytes()
    code = '''
import sys, time
from pathlib import Path
from todo_cli import models
root = Path(sys.argv[1])
store = models.TaskStore(str(root / "tasks.json"))
def pause(*args):
    (root / "ready").touch()
    time.sleep(60)
models.os.replace = pause
store.add_task("Not committed")
'''
    child = subprocess.Popen([sys.executable, "-c", code, str(tmp_path)], env=child_env())
    try:
        wait_for_files([tmp_path / "ready"], [child])
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
    assert path.read_bytes() == before
    store = TaskStore(str(path))
    store.add_task("After crash")
    assert [t.title for t in store.list_tasks()] == ["Keep", "After crash"]


def test_missing_task_is_noop_and_completion_idempotent(store):
    assert not store.delete_task(999)
    assert store.complete_task(999) is None
    assert not store.file_path.exists()
    task = store.add_task("Task")
    first = store.complete_task(task.id)
    second = store.complete_task(task.id)
    assert first.completed_at == second.completed_at


def test_invalid_update_cannot_hide_behind_value_equality(store):
    task = store.add_task("Task")
    store.complete_task(task.id)
    before = store.file_path.read_bytes()
    with pytest.raises(ValueError, match="boolean"):
        store.update_task(task.id, done=1)
    assert type(store.tasks[0].done) is bool
    assert store.file_path.read_bytes() == before


def test_duplicate_json_fields_are_not_silently_discarded(tmp_path):
    path = tmp_path / "tasks.json"
    raw = b'[{"id": 1, "title": "keep", "title": "other"}]'
    path.write_bytes(raw)
    with pytest.raises(StorageError, match="Duplicate JSON field"):
        TaskStore(str(path))
    assert path.read_bytes() == raw
