# Todo CLI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Productivity Tool](https://img.shields.io/badge/productivity-tool-green.svg)]()

A powerful command-line todo list manager with priorities, tags, and deadlines.

## 🌟 Features

- ➕ **Add Tasks** - Quick task creation with title, description, priority
- 🏷️ **Tags** - Organize tasks with custom tags
- 📅 **Due Dates** - Set deadlines for your tasks
- 🎯 **Priorities** - Low, medium, high, urgent priority levels
- ✅ **Complete** - Mark tasks as done
- 📊 **Statistics** - View your productivity stats
- 🎨 **Rich Output** - Beautiful terminal UI with colors and tables
- 💾 **Persistent** - Tasks are saved locally in JSON format
- 🐍 **Python API** - Use as a library in your code

## 📦 Installation

```bash
git clone https://github.com/Master-626/todo-cli.git
cd todo-cli
pip install .
```

## 🚀 Usage

### Add a Task
```bash
# Basic
todo add "Buy groceries"

# With priority and tags
todo add "Finish project proposal" -p high -t work -t urgent --due 2026-09-30
```

### List Tasks
```bash
# List pending tasks (default)
todo list

# Show all tasks including completed
todo list --all

# Filter by priority
todo list -p high

# Filter by tag
todo list -t work
```

### Complete a Task
```bash
todo done 1
```

### Delete a Task
```bash
todo delete 2
```

### View Statistics
```bash
todo stats
```

## 🐍 Python API

```python
from todo_cli.models import TaskStore

store = TaskStore()

# Add tasks
task = store.add_task("Write documentation", priority="high", tags=["docs"])

# List tasks
tasks = store.list_tasks(priority="high")

# Complete task
store.complete_task(task.id)

# Get stats
stats = store.get_stats()
print(f"Pending: {stats['pending']}")
```

## Storage safety

The existing JSON array format and default `~/.todo-cli/tasks.json` location are
preserved. A custom API path may be passed to `TaskStore(file_path=...)`.

- Each read and mutation takes a process lock. Mutations reload the latest file
  before changing it, so independent CLI processes and stale `TaskStore` instances
  do not overwrite each other's tasks.
- Saves use a temporary file in the same directory, flush and `fsync` it, then
  atomically replace the JSON file. An ordinary write failure leaves the prior
  file intact. In-memory changes are rolled back when a save fails.
- Invalid JSON, invalid field types, duplicate IDs, and unknown fields are errors,
  never an empty task list. Back up and repair a damaged file before retrying.
- Data and lock files must be regular files with a single hard link. Symbolic
  links (including dangling links), hard-linked files, directories, and special
  files are rejected. Parent directory aliases resolve to one canonical lock path.
- The persistent `tasks.json.lock` sidecar is intentional. Do not delete or replace
  it while any process is using the store. Lock acquisition times out after ten
  seconds with an error. Readers also require permission to create/use this file.
- New task files and replacement files are owner-only on POSIX. An abruptly killed
  writer may leave a hidden `.tasks-*.tmp` file, but the original task file remains
  readable and the OS releases its lock. A kill after replacement may have already
  committed the operation; inspect the list before retrying an uncertain add.

These guarantees apply to cooperating processes on a local filesystem with working
file locks and atomic replacement. They are not a power-loss durability guarantee
or protection against another program modifying the data, lock, or directory.
Windows uses byte-range locking and POSIX uses `flock`; network filesystems may
have different semantics. Keep a backup of important tasks.

API reads return detached task snapshots. Use `update_task` to persist changes;
IDs are immutable, unknown update fields are errors, and invalid values are
rejected. Completing an already completed task preserves its completion timestamp.
The CLI returns a nonzero status for a missing task or storage failure.

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest
```

## 📄 License

MIT License
