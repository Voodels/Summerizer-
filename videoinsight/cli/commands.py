"""
VideoInsight CLI command definitions.
"""
import os
import sys
import uuid
import threading
import time
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
from videoinsight.utils.state import create_job, get_job, list_jobs, update_job_step

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

        # Extract audio and create chunks
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Create data directories
            audio_dir = os.path.join(os.path.expanduser("~"), ".videoinsight", "audio", job_id)
            chunks_dir = os.path.join(os.path.expanduser("~"), ".videoinsight", "chunks", job_id)
            
            # Extract audio task
            extract_task = progress.add_task("[cyan]Extracting audio...", total=100)
            
            from videoinsight.utils.chunking import extract_audio, create_smart_chunks
            
            # Extract audio
            audio_path = extract_audio(
                video_path=video_info['filepath'],
                output_dir=audio_dir,
                job_id=job_id
            )
            
            if not audio_path:
                console.print("[bold red]Error:[/bold red] Failed to extract audio from video")
                sys.exit(1)
            
            progress.update(extract_task, completed=100, description="[green]Audio extracted")
            
            # Create chunks task
            chunk_task = progress.add_task("[cyan]Creating audio chunks...", total=100)
            
            # Use smart chunking for better segment boundaries
            chunks = create_smart_chunks(
                audio_path=audio_path,
                output_dir=chunks_dir,
                job_id=job_id,
                target_duration=config["transcription"]["chunk_size"] * 60,  # Convert from minutes to seconds
                overlap=config["transcription"]["overlap"]
            )
            
            if not chunks:
                console.print("[bold red]Error:[/bold red] Failed to create audio chunks")
                sys.exit(1)
            
            progress.update(chunk_task, completed=100, description=f"[green]Created {len(chunks)} chunks")

        # Check if we should start transcription
        if config.get("auto_transcribe", True):
            try:
                # Try importing the module to check if it's installed
                import faster_whisper
                has_whisper = True
            except ImportError:
                try:
                    import whisper
                    has_whisper = True
                except ImportError:
                    has_whisper = False
            
            if not has_whisper:
                console.print("[bold yellow]Warning:[/bold yellow] Transcription libraries not installed.")
                console.print("Install with: pip install faster-whisper")
                console.print(f"[bold]Job ID for resuming later:[/bold] {job_id}")
                return job_id
            
            # Start transcription
            console.print("[bold]Starting transcription...[/bold]")
            
            from videoinsight.core.transcription import transcribe_job, merge_transcriptions
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                # Start transcription task
                trans_task = progress.add_task("[cyan]Transcribing audio chunks...", total=None)
                
                # Start transcription in a separate thread so we can show progress
                def run_transcription():
                    try:
                        transcribe_job(job_id)
                    except Exception as e:
                        console.print(f"[bold red]Transcription error:[/bold red] {str(e)}")
                
                trans_thread = threading.Thread(target=run_transcription)
                trans_thread.start()
                
                # Monitor progress
                last_status = None
                while trans_thread.is_alive():
                    job = get_job(job_id)
                    if job:
                        status = job["steps"]["transcription"]["status"]
                        if status != last_status:
                            if status == "completed":
                                progress.update(trans_task, description="[green]Transcription completed")
                            elif status == "completed_with_errors":
                                progress.update(trans_task, description="[yellow]Transcription completed with some errors")
                            elif status == "failed":
                                progress.update(trans_task, description="[red]Transcription failed")
                            last_status = status
                    time.sleep(1)
                
                trans_thread.join()
            
            # Get final job status
            job = get_job(job_id)
            transcription_status = job["steps"]["transcription"]["status"]
            
            if transcription_status in ["completed", "completed_with_errors"]:
                # Merge transcriptions
                console.print("[cyan]Merging transcriptions...[/cyan]")
                try:
                    merged = merge_transcriptions(job_id)
                    if merged:
                        console.print("[bold green]Transcriptions merged successfully[/bold green]")
                        
                        # Save transcription to file
                        from videoinsight.core.transcription import save_transcription_to_file
                        output_dir = os.path.dirname(output)
                        if not output_dir:
                            output_dir = "."
                        
                        # Save both raw transcript and final output
                        transcript_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(output))[0]}_transcript.txt")
                        result = save_transcription_to_file(job_id, transcript_path)
                        
                        if result:
                            console.print(f"[bold green]Transcript saved:[/bold green] {transcript_path}")
                        
                        # Start content analysis
                        console.print("[cyan]Analyzing content...[/cyan]")
                        try:
                            from videoinsight.core.analysis import analyze_transcription
                            analysis_results = analyze_transcription(job_id)
                            if analysis_results:
                                console.print("[bold green]Content analysis completed[/bold green]")
                                
                                # Generate markdown notes
                                console.print("[cyan]Generating markdown notes...[/cyan]")
                                from videoinsight.core.markdown import generate_markdown
                                markdown_path = generate_markdown(job_id, output)
                                
                                if markdown_path:
                                    console.print(f"[bold green]Notes generated:[/bold green] {markdown_path}")
                                else:
                                    console.print("[bold red]Error:[/bold red] Failed to generate markdown notes")
                            else:
                                console.print("[bold red]Error:[/bold red] Content analysis failed")
                        except Exception as e:
                            console.print(f"[bold red]Error during analysis:[/bold red] {str(e)}")
                    else:
                        console.print("[bold red]Error:[/bold red] Failed to merge transcriptions")
                except Exception as e:
                    console.print(f"[bold red]Error merging transcriptions:[/bold red] {str(e)}")
            else:
                console.print("[bold red]Transcription was not completed successfully.[/bold red]")
                
        else:
            console.print("[yellow]Automatic transcription is disabled in configuration.[/yellow]")
        
        console.print(f"[bold]Job ID for resuming:[/bold] {job_id}")
        return job_id

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


@app.command()
def resume(
    job_id: str = typer.Argument(..., help="Job ID to resume"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reprocessing of completed steps"),
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
        
        # Check job status
        download_status = job["steps"]["download"]["status"]
        transcription_status = job["steps"]["transcription"]["status"]
        analysis_status = job["steps"]["analysis"]["status"]
        markdown_status = job["steps"]["markdown"]["status"]
        
        config = job["config"]
        
        # Resume download if needed
        if download_status != "completed" or force:
            console.print("[cyan]Resuming download...[/cyan]")
            # Code to resume download
            # This would typically retrieve the video info and check if the file exists
            
            # For now, just mark as incomplete if it's not completed
            if download_status != "completed":
                console.print("[yellow]Download step is incomplete. Please restart the process.[/yellow]")
                return
        
        # Resume transcription if needed
        if (download_status == "completed" and 
            (transcription_status not in ["completed", "completed_with_errors"] or force)):
            
            console.print("[cyan]Resuming transcription...[/cyan]")
            
            try:
                # Try importing the module to check if it's installed
                import faster_whisper
                has_whisper = True
            except ImportError:
                try:
                    import whisper
                    has_whisper = True
                except ImportError:
                    has_whisper = False
            
            if not has_whisper:
                console.print("[bold yellow]Warning:[/bold yellow] Transcription libraries not installed.")
                console.print("Install with: pip install faster-whisper")
                return
            
            from videoinsight.core.transcription import transcribe_job, merge_transcriptions
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                # Start transcription task
                task = progress.add_task("[cyan]Transcribing audio chunks...", total=None)
                
                # Start transcription in a separate thread so we can show progress
                def run_transcription():
                    try:
                        transcribe_job(job_id)
                    except Exception as e:
                        console.print(f"[bold red]Transcription error:[/bold red] {str(e)}")
                
                trans_thread = threading.Thread(target=run_transcription)
                trans_thread.start()
                
                # Monitor progress
                last_status = None
                while trans_thread.is_alive():
                    job = get_job(job_id)
                    if job:
                        status = job["steps"]["transcription"]["status"]
                        if status != last_status:
                            if status == "completed":
                                progress.update(task, description="[green]Transcription completed")
                            elif status == "completed_with_errors":
                                progress.update(task, description="[yellow]Transcription completed with some errors")
                            elif status == "failed":
                                progress.update(task, description="[red]Transcription failed")
                            last_status = status
                    time.sleep(1)
                
                trans_thread.join()
            
            # Merge transcriptions
            console.print("[cyan]Merging transcriptions...[/cyan]")
            try:
                merged = merge_transcriptions(job_id)
                if merged:
                    console.print("[bold green]Transcriptions merged successfully[/bold green]")
                    
                    # Save transcription to file
                    from videoinsight.core.transcription import save_transcription_to_file
                    output_path = job["output_path"]
                    output_dir = os.path.dirname(output_path)
                    if not output_dir:
                        output_dir = "."
                    
                    # Save both raw transcript and final output
                    transcript_path = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(output_path))[0]}_transcript.txt")
                    result = save_transcription_to_file(job_id, transcript_path)
                    
                    if result:
                        console.print(f"[bold green]Transcript saved:[/bold green] {transcript_path}")
                else:
                    console.print("[bold red]Error:[/bold red] Failed to merge transcriptions")
            except Exception as e:
                console.print(f"[bold red]Error merging transcriptions:[/bold red] {str(e)}")
        
        # Resume analysis if needed
        if ((transcription_status == "completed" or transcription_status == "completed_with_errors") and 
            (analysis_status != "completed" or force)):
            
            console.print("[cyan]Running content analysis...[/cyan]")
            
            try:
                from videoinsight.core.analysis import analyze_transcription
                analysis_results = analyze_transcription(job_id)
                if analysis_results:
                    console.print("[bold green]Content analysis completed[/bold green]")
                else:
                    console.print("[bold red]Error:[/bold red] Content analysis failed")
            except Exception as e:
                console.print(f"[bold red]Error during analysis:[/bold red] {str(e)}")
                
        # Resume markdown generation if needed
        if (analysis_status == "completed" and 
            (markdown_status != "completed" or force)):
            
            console.print("[cyan]Generating markdown notes...[/cyan]")
            try:
                from videoinsight.core.markdown import generate_markdown
                output_path = job["output_path"]
                markdown_path = generate_markdown(job_id, output_path)
                
                if markdown_path:
                    console.print(f"[bold green]Notes generated:[/bold green] {markdown_path}")
                else:
                    console.print("[bold red]Error:[/bold red] Failed to generate markdown notes")
            except Exception as e:
                console.print(f"[bold red]Error generating markdown:[/bold red] {str(e)}")
        
        console.print(f"[bold]Job completed to stage:[/bold] {get_current_stage(job)}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)


def get_current_stage(job):
    """Helper function to determine the current stage of a job."""
    if job["steps"]["markdown"]["status"] == "completed":
        return "markdown"
    elif job["steps"]["analysis"]["status"] == "completed":
        return "analysis"
    elif job["steps"]["transcription"]["status"] in ["completed", "completed_with_errors"]:
        return "transcription"
    elif job["steps"]["download"]["status"] == "completed":
        return "download"
    else:
        return "created"


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