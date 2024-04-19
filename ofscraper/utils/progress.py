from rich.console import Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.style import Style
from rich.table import Column

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.console as console_
from ofscraper.classes.multiprocessprogress import MultiprocessProgress as MultiProgress


def setup_all_paid_live():
    global all_paid_progress
    global overall_progress
    all_paid_progress = Progress("{task.description}")
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("{task.description}"),
    )
    progress_group = Group(overall_progress, Panel(Group(all_paid_progress)))

    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def setup_api_split_progress_live():
    global timeline_layout
    global pinned_layout
    global archived_layout
    global labelled_layout
    global messages_layout
    global paid_layout
    global stories_layout
    global highlights_layout
    set_up_progress()
    setup_layout()

    layout = Layout(name="parent")
    layout.split_column(Layout(name="upper", ratio=1), Layout(name="lower", ratio=1))
    layout["upper"].split_row(
        timeline_layout,
        pinned_layout,
        archived_layout,
        labelled_layout,
        Layout(name="OF-Scraper", size=0, ratio=0),
    ),
    layout["lower"].split_row(
        messages_layout,
        paid_layout,
        stories_layout,
        highlights_layout,
        Layout(name="OF-Scaper", size=0, ratio=0),
    )

    progress_group = Group(overall_progress, layout)
    return Live(progress_group, console=console_.get_shared_console())


def setup_layout():
    global timeline_progress
    global pinned_progress
    global overall_progress
    global archived_progress
    global messages_progress
    global paid_progress
    global labelled_progress
    global highlights_progress
    global stories_progress
    global timeline_layout
    global pinned_layout
    global archived_layout
    global labelled_layout
    global messages_layout
    global paid_layout
    global stories_layout
    global highlights_layout

    timeline_layout = Layout(
        Panel(timeline_progress, title="Timeline Info"), name="timeline"
    )
    pinned_layout = Layout(Panel(pinned_progress, title="Pinned Info"), name="pinned")
    archived_layout = Layout(
        Panel(archived_progress, title="Archived Info"), name="archived"
    )
    labelled_layout = Layout(
        Panel(labelled_progress, title="Labelled Info"), name="labelled"
    )
    messages_layout = Layout(
        Panel(messages_progress, title="Messages Info"), name="messages"
    )
    paid_layout = Layout(Panel(paid_progress, title="Paid Info"), name="paid")
    stories_layout = Layout(
        Panel(stories_progress, title="Stories Info"), name="stories"
    )
    highlights_layout = Layout(
        Panel(highlights_progress, title="Highlights Info"), name="highlights"
    )

    timeline_layout.visible = False
    pinned_layout.visible = False
    archived_layout.visible = False
    labelled_layout.visible = False
    messages_layout.visible = False
    paid_layout.visible = False
    stories_layout.visible = False
    highlights_layout.visible = False


def set_up_progress():
    global timeline_progress
    global pinned_progress
    global overall_progress
    global archived_progress
    global messages_progress
    global paid_progress
    global labelled_progress
    global highlights_progress
    global stories_progress
    timeline_progress = Progress("{task.description}")
    pinned_progress = Progress("{task.description}")
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn("{task.description}"),
    )
    archived_progress = Progress("{task.description}")
    messages_progress = Progress("{task.description}")
    paid_progress = Progress("{task.description}")
    labelled_progress = Progress("{task.description}")
    highlights_progress = Progress("{task.description}")
    stories_progress = Progress("{task.description}")


def setupDownloadProgressBar(multi=False):
    downloadprogress = (
        config_data.get_show_downloadprogress() or read_args.retriveArgs().downloadbars
    )
    if not multi:
        job_progress = Progress(
            TextColumn("{task.description}", table_column=Column(ratio=2)),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TransferSpeedColumn(),
            DownloadColumn(),
        )
    else:
        job_progress = MultiProgress(
            TextColumn("{task.description}", table_column=Column(ratio=2)),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            TransferSpeedColumn(),
            DownloadColumn(),
        )
    overall_progress = Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    )
    progress_group = Group(overall_progress, Panel(Group(job_progress, fit=True)))
    progress_group.renderables[1].height = (
        max(15, console_.get_shared_console().size[1] - 2) if downloadprogress else 0
    )
    return progress_group, overall_progress, job_progress


def set_up_api_timeline():
    global overall_progress
    global timeline_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting timeline posts...\n{{task.description}}"),
    )
    timeline_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(timeline_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_pinned():
    global overall_progress
    global pinned_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting pinned posts...\n{{task.description}}"),
    )
    pinned_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(pinned_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_paid():
    global overall_progress
    global paid_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting paid posts...\n{{task.description}}"),
    )
    paid_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(paid_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_messages():
    global overall_progress
    global messages_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting messages...\n{{task.description}}"),
    )
    messages_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(messages_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_archived():
    global overall_progress
    global archived_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting archived...\n{{task.description}}"),
    )
    archived_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(archived_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_stories():
    global overall_progress
    global stories_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting stories...\n{{task.description}}"),
    )
    stories_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(stories_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_highlights_lists():
    global overall_progress
    global highlights_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting highlights lists...\n{{task.description}}"),
    )
    highlights_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(highlights_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_highlights():
    global overall_progress
    global highlights_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting highlights via list..\n{{task.description}}"),
    )
    highlights_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(highlights_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_labels():
    global overall_progress
    global labelled_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting Labels\n{{task.description}}"),
    )
    labelled_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(labelled_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )


def set_up_api_posts_labels():
    global overall_progress
    global labelled_progress
    overall_progress = Progress(
        SpinnerColumn(style=Style(color="blue")),
        TextColumn(f"Getting Posts via labels\n{{task.description}}"),
    )
    labelled_progress = Progress("{task.description}")
    progress_group = Group(overall_progress, Panel(Group(labelled_progress)))
    return Live(
        progress_group, refresh_per_second=5, console=console_.get_shared_console()
    )
