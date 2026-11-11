# Todo CLI

## 概要

`todo-cli` 是一个本地命令行待办工具，用来添加、列出、完成和删除任务，并查看统计。每条任务可以带优先级、标签和截止日期，数据以 JSON 保存在 `~/.todo-cli/tasks.json`。多个进程通过文件锁和原子替换安全地更新同一份清单。下文为英文说明。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Productivity Tool](https://img.shields.io/badge/productivity-tool-green.svg)]()

A local command-line todo list. Tasks have a priority, tags, and an optional due date, and they are stored in a JSON file that cooperating processes can update safely.

The `todo` and `todo-cli` commands are the same program. `TaskStore` is the library API.

## Features

- Add a task with a title, description, priority, tags, and due date
- List pending tasks, or include completed ones
- Filter by priority or tag, and list tasks that are overdue
- Mark a task done, or delete it
- Show counts by status and pending priority
- Save tasks as JSON under `~/.todo-cli/tasks.json`
- Use the same operations from Python

## Installation

Python 3.8 or newer is required.

```bash
git clone https://github.com/Master-626/todo-cli.git
cd todo-cli
pip install .
```

Install the development extra to run the tests and the linter:

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Title only. Priority defaults to medium.
todo add "Buy groceries"

# Description, priority, tags, and a calendar due date.
todo add "Finish project proposal" -d "First draft" -p high -t work -t urgent --due 2026-09-30

# Pending tasks.
todo list

# Completed tasks too, or only one priority / tag.
todo list --all
todo list -p high
todo list -t work

# Pending tasks whose YYYY-MM-DD due date is before today.
todo list --overdue

todo done 1
todo delete 2
todo stats
```

`todo list --overdue -p high -t work` combines the filters. A task due today is not overdue. Text that is not a canonical `YYYY-MM-DD` date is stored unchanged and is not treated as overdue. Completed tasks are never overdue.

## Commands and options

| Command | Option | Meaning |
| --- | --- | --- |
| `todo add TITLE` | `-d, --description TEXT` | Optional description. Default: empty. |
| | `-p, --priority CHOICE` | `low`, `medium`, `high`, or `urgent`. Default: `medium`. |
| | `-t, --tag TEXT` | Tag. Repeat for more than one. An empty tag is stored as an empty tag. |
| | `--due TEXT` | Due text. `YYYY-MM-DD` is the form `--overdue` understands. |
| `todo list` | `--all` | Include completed tasks. The default list is pending only. |
| | `-p, --priority CHOICE` | Exact priority. Unknown values are an error. |
| | `-t, --tag TEXT` | Exact tag. An empty value matches only empty tags. |
| | `--overdue` | Pending tasks with a `YYYY-MM-DD` due date before today. |
| `todo done ID` | | Mark task `ID` done. A missing id exits nonzero. Doing it again keeps the original completion time. |
| `todo delete ID` | | Delete task `ID`. A missing id exits nonzero. |
| `todo stats` | | Total, completed, pending, and pending counts by priority. |
| `todo --version` | | Print the version and exit. |

Ids shown in `todo list` are the full integers to pass to `done` and `delete`.

The library list includes completed tasks unless you pass `include_done=False`. The CLI hides them unless you pass `--all`.

## Python API

```python
from todo_cli.models import TaskStore

store = TaskStore()  # or TaskStore("/path/to/tasks.json")

task = store.add_task(
    "Write documentation",
    description="API examples",
    priority="high",
    tags=["docs"],
    due_date="2026-09-30",
)

pending = store.list_tasks(include_done=False, priority="high", tag="docs")
overdue = store.list_tasks(overdue=True)
store.complete_task(task.id)
store.delete_task(task.id)
stats = store.get_stats()
print(stats["pending"], stats["by_priority"]["high"])
```

`list_tasks` treats `priority=None` and `tag=None` as "no filter". Any other value is matched exactly, including an empty tag. `get_task`, `complete_task`, `delete_task`, and `update_task` require a real `int` id. `True` and `1.0` are rejected instead of selecting task 1.

Reads return detached snapshots. Persist edits with `update_task`. Ids cannot be changed, unknown fields are errors, and invalid values are rejected. A task added through `add_task` stores `created_at` as a local timestamp. A missing or JSON `null` `created_at` stays null.

## Storage safety

The JSON array format and the default `~/.todo-cli/tasks.json` location are unchanged. Pass another path to `TaskStore(file_path=...)`.

- Each read and mutation takes a process lock. Mutations reload the latest file before changing it, so independent CLI processes and stale `TaskStore` instances do not overwrite each other's tasks.
- Saves use a temporary file in the same directory, flush and `fsync` it, then atomically replace the JSON file. An ordinary write failure leaves the prior file intact. In-memory changes are rolled back when a save fails.
- Invalid JSON, invalid field types, duplicate IDs, and unknown fields are errors, never an empty task list. Back up and repair a damaged file before retrying.
- An omitted `tags` field means no tags. JSON `null` for `tags` is invalid and is not coerced to `[]`.
- A missing or null `created_at` is not replaced with the current time on read or on a later save.
- Data and lock files must be regular files with a single hard link. Symbolic links (including dangling links), hard-linked files, directories, and special files are rejected. Parent directory aliases resolve to one canonical lock path.
- The persistent `tasks.json.lock` sidecar is intentional. Do not delete or replace it while any process is using the store. Lock acquisition times out after ten seconds with an error. Readers also require permission to create or use this file.
- New task files and replacement files are owner-only on POSIX. An abruptly killed writer may leave a hidden `.tasks-*.tmp` file, but the original task file remains readable and the OS releases its lock. A kill after replacement may have already committed the operation; inspect the list before retrying an uncertain add.

These guarantees apply to cooperating processes on a local filesystem with working file locks and atomic replacement. They are not a power-loss durability guarantee or protection against another program modifying the data, lock, or directory. Windows uses byte-range locking and POSIX uses `flock`; network filesystems may have different semantics. Keep a backup of important tasks.

On legacy terminal encodings, unsupported output characters are escaped instead of causing an error after a successful save. Task files remain UTF-8. The CLI returns a nonzero status for a missing task, an unknown list priority, or a storage failure.

## Testing

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

GitHub Actions runs `ruff check` and `pytest` on Python 3.8 through 3.13, on Ubuntu and Windows.

## License

MIT License
