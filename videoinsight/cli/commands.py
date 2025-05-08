"""
VideoInsight CLI command definitions.
"""
import os
import sys
import uuid
from typing import Optional
import typer
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)

from videoinsight.cli.config import load_config, save_config
from videoinsight.core.downloader import download_video
from videoinsight.utils.state import create_job, get_job, list_jobs

# Create Typer app
app = typer.Typer(
    name="videoinsight",
    help="Generate comprehensive notes from YouTube videos",
    add_completion=False,
)

console = Console()


@app.command()
def process(
    url: str = typer.Argument(..., help="YouTube video URL"),
    output: str = typer.Option("notes.md", "--output", "-o", help="Output file path"),
    quality: str = typer.Option("medium", "--quality", "-q", help="Transcription quality (low, medium, high)"),
    detail: str = typer.Option("standard", "--detail", "-d", help="Note detail level (summary, standard, comprehensive)"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Force language (ISO code, e.g., 'en')"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reprocessing of existing files"),
):
    """
    Process a YouTube video and generate comprehensive notes.
    """
    try:
        # Load configuration
        config = load_config()

        # Create a job ID
        job_id = str(uuid.uuid4())

        # Map quality levels to model sizes
        quality_to_model = {
            "low": "tiny",
            "medium": "base",
            "high": "small",
        }

        config["transcription"]["model"] = quality_to_model.get(quality, "base")

        if language:
            config["transcription"]["language"] = language

        # Create job
        job = create_job(job_id, url, output, config)

        console.print(f"[bold green]Created job:[/bold green] {job_id}")
        console.print(f"[bold]Video URL:[/bold] {url}")

        # Download video
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Downloading video...", total=100)

            def progress_hook(d):
                if d["status"] == "downloading":
                    p = d.get("_percent_str", "0%").strip("%")
                    try:
                        progress.update(task, completed=float(p))
                    except:
                        pass
                elif d["status"] == "finished":
                    progress.update(task, completed=100)

            video_info = download_video(url, config, progress_hook)

        console.print(f"[bold green]Download complete:[/bold green] {video_info['title']}")
        console.print(f"Duration: {video_info['duration_string']}")

        # TODO: Transcription and analysis
        console.print("[yellow]Transcription and analysis not yet implemented.[/yellow]")
        console.print(f"[bold]Job ID for resuming:[/bold] {job_id}")

        return job_id

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def resume(
    job_id: str = typer.Argument(..., help="Job ID to resume"),
):
    """
    Resume a previously interrupted job.
    """
    try:
        job = get_job(job_id)
        if not job:
            console.print(f"[bold red]Error:[/bold red] Job {job_id} not found.")
            sys.exit(1)

        console.print(f"[bold green]Resuming job:[/bold green] {job_id}")
        console.print(f"[bold]Video URL:[/bold] {job['url']}")
        # TODO: Resume functionality
        console.print("[yellow]Resume functionality not yet implemented.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def list():
    """
    List all jobs.
    """
    try:
        jobs = list_jobs()
        if not jobs:
            console.print("[yellow]No jobs found.[/yellow]")
            return

        console.print("[bold]Available jobs:[/bold]")
        for job in jobs:
            status_color = {
                "completed": "green",
                "in_progress": "yellow",
                "failed": "red",
            }.get(job["status"], "white")

            console.print(f"[bold]{job['id']}[/bold] - [bold {status_color}]{job['status']}[/bold {status_color}]")
            console.print(f"  URL: {job['url']}")
            console.print(f"  Created: {job['created_at']}")
            console.print()

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    reset: bool = typer.Option(False, "--reset", help="Reset to default configuration"),
):
    """
    Configure VideoInsight settings.
    """
    try:
        current_config = load_config()

        if reset:
            from shutil import copyfile
            import videoinsight

            config_dir = os.path.dirname(os.path.dirname(videoinsight.__file__))
            default_config = os.path.join(config_dir, "videoinsight", "config", "default.yaml")
            user_config = os.path.join(os.path.expanduser("~"), ".videoinsight", "config.yaml")

            os.makedirs(os.path.dirname(user_config), exist_ok=True)
            copyfile(default_config, user_config)

            console.print("[bold green]Configuration reset to defaults.[/bold green]")
            return

        if show:
            import yaml
            console.print("[bold]Current configuration:[/bold]")
            console.print(yaml.dump(current_config))
            return

        console.print("[yellow]Interactive configuration not yet implemented.[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    app()
