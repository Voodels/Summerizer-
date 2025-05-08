"""
YouTube video downloading functionality.
"""
import os
from typing import Dict, Any, Callable, Optional
import yt_dlp

def format_duration(seconds: int) -> str:
    """
    Format seconds into a human-readable duration string.

    Args:
        seconds (int): Duration in seconds
    
    Returns:
        str: Formatted duration string (HH:MM:SS)
    """
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

def download_video(
    url: str,
    config: Dict[str, Any],
    progress_hook: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Download a YouTube video using yt-dlp.

    Args:
        url (str): YouTube video URL
        config (Dict[str, Any]): Configuration dictionary
        progress_hook (Optional[Callable]): Progress callback function
    
    Returns:
        Dict[str, Any]: Video information
    """
    # Ensure download directory exists
    output_dir = os.path.dirname(config["download"]["output_template"])
    os.makedirs(output_dir, exist_ok=True)

    # Configure yt-dlp options
    ydl_opts = {
        'format': config["download"]["format"],
        'outtmpl': config["download"]["output_template"],
        'retries': config["download"]["retries"],
        'socket_timeout': config["download"]["timeout"],
        'ratelimit': config["download"]["rate_limit"] if config["download"]["rate_limit"] > 0 else None,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,  # We'll handle progress ourselves
    }

    # Add progress hook if provided
    if progress_hook:
        ydl_opts['progress_hooks'] = [progress_hook]

    # Download the video and extract info
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Process video information
    video_info = {
        'id': info.get('id'),
        'title': info.get('title'),
        'duration': info.get('duration'),
        'duration_string': format_duration(info.get('duration', 0)),
        'channel': info.get('channel'),
        'upload_date': info.get('upload_date'),
        'filepath': ydl.prepare_filename(info),
        'description': info.get('description'),
        'categories': info.get('categories', []),
        'tags': info.get('tags', []),
        'chapters': info.get('chapters', []),
        'url': url,
    }

    return video_info

def get_video_info(url: str) -> Dict[str, Any]:
    """
    Get information about a YouTube video without downloading it.

    Args:
        url (str): YouTube video URL
    
    Returns:
        Dict[str, Any]: Video information
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Process video information
    video_info = {
        'id': info.get('id'),
        'title': info.get('title'),
        'duration': info.get('duration'),
        'duration_string': format_duration(info.get('duration', 0)),
        'channel': info.get('channel'),
        'upload_date': info.get('upload_date'),
        'description': info.get('description'),
        'categories': info.get('categories', []),
        'tags': info.get('tags', []),
        'chapters': info.get('chapters', []),
        'url': url,
    }

    return video_info
