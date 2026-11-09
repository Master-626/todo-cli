"""
CLI interface for todo-cli.
"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .models import StorageError, TaskStore

console = Console()


class SafeGroup(click.Group):
    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (StorageError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc


@click.group(cls=SafeGroup)
@click.version_option(version="0.1.0")
@click.pass_context
def main(ctx):
    """Todo CLI - Powerful command-line todo list manager."""
    ctx.ensure_object(dict)
    ctx.obj["store"] = TaskStore()


@main.command()
@click.argument("title")
@click.option("--description", "-d", default="", help="Task description")
@click.option("--priority", "-p", default="medium",
              type=click.Choice(["low", "medium", "high", "urgent"]),
              help="Task priority")
@click.option("--tag", "-t", multiple=True, help="Task tags (can be used multiple times)")
@click.option("--due", help="Due date (YYYY-MM-DD)")
@click.pass_context
def add(ctx, title, description, priority, tag, due):
    """Add a new task."""
    store = ctx.obj["store"]
    task = store.add_task(
        title=title,
        description=description,
        priority=priority,
        tags=list(tag),
        due_date=due,
    )
    console.print(f"✅ Added task #{task.id}: ", Text(task.title, style="bold green"), sep="")


@main.command(name="list")
@click.option("--all", "show_all", is_flag=True, help="Show all tasks (including completed)")
@click.option("--priority", "-p", help="Filter by priority")
@click.option("--tag", "-t", help="Filter by tag")
@click.pass_context
def list_tasks(ctx, show_all, priority, tag):
    """List tasks."""
    store = ctx.obj["store"]
    tasks = store.list_tasks(include_done=show_all, priority=priority, tag=tag)

    if not tasks:
        console.print("📭 No tasks found")
        return

    table = Table(title="Todo List")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Status", width=6)
    table.add_column("Priority", width=8)
    table.add_column("Title", style="green")
    table.add_column("Tags", width=15)
    table.add_column("Due", width=12)

    for task in tasks:
        status = "✅" if task.done else "⬜"
        priority_color = {
            "low": "blue",
            "medium": "yellow",
            "high": "orange3",
            "urgent": "red",
        }.get(task.priority, "white")

        tags_str = ", ".join(task.tags) if task.tags else ""
        due_str = task.due_date or ""

        table.add_row(
            str(task.id),
            status,
            f"[{priority_color}]{task.priority}[/{priority_color}]",
            Text(task.title),
            Text(tags_str),
            Text(due_str),
        )

    console.print(table)


@main.command()
@click.argument("task_id", type=int)
@click.pass_context
def done(ctx, task_id):
    """Mark a task as completed."""
    store = ctx.obj["store"]
    task = store.complete_task(task_id)
    if task:
        console.print(f"✅ Completed task #{task_id}: ", Text(task.title, style="bold green"), sep="")
    else:
        raise click.ClickException(f"Task #{task_id} not found")


@main.command()
@click.argument("task_id", type=int)
@click.pass_context
def delete(ctx, task_id):
    """Delete a task."""
    store = ctx.obj["store"]
    if store.delete_task(task_id):
        console.print(f"🗑️  Deleted task #{task_id}")
    else:
        raise click.ClickException(f"Task #{task_id} not found")


@main.command()
@click.pass_context
def stats(ctx):
    """Show task statistics."""
    store = ctx.obj["store"]
    stats = store.get_stats()

    console.print(Panel.fit(
        f"[bold cyan]Task Statistics[/bold cyan]\n\n"
        f"Total: {stats['total']}\n"
        f"Completed: {stats['completed']}\n"
        f"Pending: {stats['pending']}\n\n"
        f"By Priority (pending):\n"
        f"  🔴 Urgent: {stats['by_priority']['urgent']}\n"
        f"  🟠 High: {stats['by_priority']['high']}\n"
        f"  🟡 Medium: {stats['by_priority']['medium']}\n"
        f"  🔵 Low: {stats['by_priority']['low']}",
        border_style="blue"
    ))


if __name__ == "__main__":
    main()
