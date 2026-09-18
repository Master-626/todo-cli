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
todo add "Finish project proposal" -p high -t work urgent --due 2026-09-30
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

## 🧪 Testing

```bash
pip install -e ".[dev]"
pytest
```

## 📄 License

MIT License
