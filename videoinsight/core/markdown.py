"""
Markdown generation module for VideoInsight.

This module creates formatted markdown notes from transcriptions and analysis.
"""
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from videoinsight.utils.state import get_job, update_job_step


def format_timestamp(ms: int) -> str:
    """
    Format milliseconds into a readable timestamp (MM:SS or HH:MM:SS).
    
    Args:
        ms: Time in milliseconds
        
    Returns:
        Formatted timestamp string
    """
    total_seconds = ms / 1000
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


def generate_markdown(job_id: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Generate comprehensive markdown notes from transcription and analysis.
    
    Args:
        job_id: ID of the job
        output_path: Path to save the markdown file
        
    Returns:
        Path to the generated markdown file
    """
    # Get job data
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Check if we have the necessary data
    if job["steps"]["analysis"]["status"] != "completed":
        raise ValueError("Analysis step must be completed first")
    
    # Update job status
    update_job_step(job_id, "markdown", "in_progress", {"message": "Generating markdown notes"})
    
    try:
        # Get transcription and analysis data
        transcription = job["steps"]["analysis"]["data"]["merged_transcription"]
        analysis = job["steps"]["analysis"]["data"]["analysis"]
        
        # If output_path is not specified, use the one from the job
        if not output_path:
            output_path = job["output_path"]
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        # Generate the markdown content
        markdown_content = _generate_markdown_content(job, transcription, analysis)
        
        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        
        # Update job status
        update_job_step(job_id, "markdown", "completed", {
            "message": "Markdown generated",
            "output_path": output_path
        })
        
        return output_path
        
    except Exception as e:
        update_job_step(job_id, "markdown", "failed", {"error": str(e)})
        raise


def _generate_markdown_content(
    job: Dict[str, Any],
    transcription: Dict[str, Any], 
    analysis: Dict[str, Any]
) -> str:
    """Generate the content of the markdown file."""
    # Get video information
    video_url = job["url"]
    video_title = job["steps"]["download"]["data"]["title"] if "title" in job["steps"]["download"]["data"] else "Untitled Video"
    video_author = job["steps"]["download"]["data"].get("uploader", "Unknown Author")
    
    # Get the current date
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Start building the markdown
    markdown = f"# {video_title}\n\n"
    markdown += f"_Notes generated by VideoInsight on {current_date}_\n\n"
    
    # Add video metadata
    markdown += "## Video Information\n\n"
    markdown += f"- **Source**: [{video_author}]({video_url})\n"
    
    if "duration_string" in job["steps"]["download"]["data"]:
        markdown += f"- **Duration**: {job['steps']['download']['data']['duration_string']}\n"
    
    if "language" in transcription:
        markdown += f"- **Language**: {transcription['language']}\n"
    
    markdown += "\n"
    
    # Add key topics section
    markdown += "## Key Topics\n\n"
    
    for topic in analysis["topics"][:10]:  # Top 10 topics
        markdown += f"- **{topic['keyword'].capitalize()}** _{topic['frequency']} mentions_\n"
    
    markdown += "\n"
    
    # Add content outline
    markdown += "## Content Outline\n\n"
    
    for section in analysis["outline"]["sections"]:
        section_time = format_timestamp(section["start"])
        markdown += f"- [{section_time}](#section-{section['number']}) {section['title']}\n"
    
    markdown += "\n"
    
    # Add detailed content sections
    markdown += "## Detailed Content\n\n"
    
    for section in analysis["outline"]["sections"]:
        section_time = format_timestamp(section["start"])
        markdown += f"### <a id=\"section-{section['number']}\"></a>[{section_time}] {section['title']}\n\n"
        
        # Find all segments that belong to this section
        relevant_segments = []
        for segment in transcription["segments"]:
            if section["start"] <= segment["start"] < section["end"]:
                relevant_segments.append(segment)
        
        # Group segments into paragraphs (simple approach: join segments with less than 1s gap)
        paragraphs = []
        current_paragraph = ""
        
        for i, segment in enumerate(relevant_segments):
            if i > 0 and segment["start"] - relevant_segments[i-1]["end"] > 1000:  # 1000ms = 1s gap
                paragraphs.append(current_paragraph.strip())
                current_paragraph = ""
            
            timestamp = format_timestamp(segment["start"])
            current_paragraph += f"[{timestamp}] {segment['text']} "
        
        # Add the last paragraph
        if current_paragraph:
            paragraphs.append(current_paragraph.strip())
        
        # Add paragraphs to markdown
        for paragraph in paragraphs:
            markdown += f"{paragraph}\n\n"
    
    # Add footer
    markdown += "---\n\n"
    markdown += "_Generated by VideoInsight CLI - Automated YouTube Notes_\n"
    
    return markdown