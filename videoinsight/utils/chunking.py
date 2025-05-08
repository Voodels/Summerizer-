"""
Audio chunking functionality for VideoInsight.

This module handles extracting audio from videos and splitting
it into manageable chunks for processing.
"""
import os
import subprocess
import math
import json
from typing import Dict, Any, List, Optional, Tuple

from videoinsight.utils.state import update_job_step, add_chunk


def extract_audio(
    video_path: str,
    output_dir: str,
    job_id: str,
    format: str = "wav",
    sample_rate: int = 16000,
    channels: int = 1,
) -> Optional[str]:
    """
    Extract audio from a video file using ffmpeg.

    Args:
        video_path (str): Path to the video file
        output_dir (str): Directory to save the extracted audio
        job_id (str): Job ID for tracking
        format (str, optional): Audio format. Defaults to "wav".
        sample_rate (int, optional): Audio sample rate. Defaults to 16000.
        channels (int, optional): Number of audio channels. Defaults to 1.

    Returns:
        Optional[str]: Path to the extracted audio file, or None if failed
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Prepare file paths
    audio_filename = f"{os.path.splitext(os.path.basename(video_path))[0]}.{format}"
    audio_path = os.path.join(output_dir, audio_filename)

    try:
        # Update job status
        update_job_step(
            job_id, 
            "download", 
            "in_progress", 
            {"message": "Extracting audio", "audio_path": audio_path}
        )

        # Construct ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output files
            "-i", video_path,
            "-vn",  # Disable video
            "-acodec", "pcm_s16le" if format == "wav" else format,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            audio_path
        ]

        # Run ffmpeg command
        subprocess.run(cmd, check=True, capture_output=True)

        # Verify file was created
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            update_job_step(
                job_id,
                "download",
                "failed",
                {"error": "Failed to extract audio: Output file is empty or missing"}
            )
            return None

        # Update job status
        update_job_step(
            job_id,
            "download",
            "completed",
            {"message": "Audio extraction completed", "audio_path": audio_path}
        )

        return audio_path

    except subprocess.CalledProcessError as e:
        error_message = f"ffmpeg error: {e.stderr.decode() if e.stderr else str(e)}"
        update_job_step(job_id, "download", "failed", {"error": error_message})
        return None
    except Exception as e:
        update_job_step(job_id, "download", "failed", {"error": str(e)})
        return None


def get_audio_duration(audio_path: str) -> Optional[float]:
    """
    Get the duration of an audio file using ffprobe.

    Args:
        audio_path (str): Path to the audio file

    Returns:
        Optional[float]: Duration in seconds, or None if failed
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        return float(data["format"]["duration"])
    
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        print(f"Error getting audio duration: {str(e)}")
        return None


def create_chunks(
    audio_path: str,
    output_dir: str,
    job_id: str,
    chunk_duration: int = 30 * 60,  # 30 minutes
    overlap: int = 5,  # 5 seconds
    format: str = "wav",
) -> List[Dict[str, Any]]:
    """
    Split an audio file into overlapping chunks.

    Args:
        audio_path (str): Path to the audio file
        output_dir (str): Directory to save the chunks
        job_id (str): Job ID for tracking
        chunk_duration (int, optional): Duration of each chunk in seconds. Defaults to 30*60 (30 minutes).
        overlap (int, optional): Overlap between chunks in seconds. Defaults to 5.
        format (str, optional): Output audio format. Defaults to "wav".

    Returns:
        List[Dict[str, Any]]: List of chunk metadata
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get audio duration
    duration = get_audio_duration(audio_path)
    if not duration:
        update_job_step(job_id, "transcription", "failed", {"error": "Could not determine audio duration"})
        return []
    
    # Calculate number of chunks
    effective_chunk_duration = chunk_duration - overlap
    num_chunks = math.ceil(duration / effective_chunk_duration)
    
    # Update job status
    update_job_step(
        job_id,
        "transcription",
        "in_progress",
        {
            "message": f"Creating {num_chunks} audio chunks",
            "total_chunks": num_chunks,
            "duration": duration
        }
    )
    
    chunks = []
    
    for i in range(num_chunks):
        # Calculate start and end times
        start_time = i * effective_chunk_duration
        
        # For the last chunk, ensure it goes to the end of the file
        if i == num_chunks - 1:
            end_time = duration
        else:
            end_time = start_time + chunk_duration
            # Ensure we don't go past the end of the file
            if end_time > duration:
                end_time = duration
        
        # Generate chunk ID and filename
        chunk_id = f"{job_id}_chunk_{i+1:03d}"
        chunk_filename = f"{os.path.splitext(os.path.basename(audio_path))[0]}_chunk_{i+1:03d}.{format}"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        # Create the chunk
        if create_audio_chunk(audio_path, chunk_path, start_time, end_time):
            # Create chunk metadata
            chunk_data = {
                "id": chunk_id,
                "path": chunk_path,
                "start_time": start_time * 1000,  # Convert to milliseconds
                "end_time": end_time * 1000,      # Convert to milliseconds
                "sequence": i + 1
            }
            
            # Add chunk to job state
            add_chunk(job_id, chunk_id, start_time * 1000, end_time * 1000)
            
            # Add to list
            chunks.append(chunk_data)
            
    # Update job status
    update_job_step(
        job_id,
        "transcription",
        "in_progress",
        {
            "message": f"Created {len(chunks)} audio chunks",
            "chunks_created": len(chunks)
        }
    )
    
    return chunks


def create_audio_chunk(
    audio_path: str,
    output_path: str,
    start_time: float,
    end_time: float
) -> bool:
    """
    Create an audio chunk from a larger audio file.

    Args:
        audio_path (str): Path to the source audio file
        output_path (str): Path for the output chunk
        start_time (float): Start time in seconds
        end_time (float): End time in seconds

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Calculate duration
        duration = end_time - start_time
        
        # Construct ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",                  # Overwrite output files
            "-ss", str(start_time),  # Start time
            "-i", audio_path,      # Input file
            "-t", str(duration),   # Duration
            "-c", "copy",          # Copy codec (no re-encoding)
            output_path            # Output file
        ]
        
        # Run ffmpeg command
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Verify file was created
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            print(f"Failed to create chunk {output_path}: Output file is empty or missing")
            return False
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"ffmpeg error creating chunk: {e.stderr.decode() if e.stderr else str(e)}")
        return False
    except Exception as e:
        print(f"Error creating audio chunk: {str(e)}")
        return False


def detect_silence(
    audio_path: str,
    noise_threshold: float = -30.0,
    min_silence_duration: float = 1.0
) -> List[Tuple[float, float]]:
    """
    Detect periods of silence in an audio file.
    Useful for finding natural break points for chunking.

    Args:
        audio_path (str): Path to the audio file
        noise_threshold (float, optional): Silence threshold in dB. Defaults to -30.0.
        min_silence_duration (float, optional): Minimum silence duration in seconds. Defaults to 1.0.

    Returns:
        List[Tuple[float, float]]: List of (start_time, end_time) for silence periods
    """
    try:
        cmd = [
            "ffmpeg",
            "-i", audio_path,
            "-af", f"silencedetect=noise={noise_threshold}dB:d={min_silence_duration}",
            "-f", "null",
            "-"
        ]
        
        # Run ffmpeg command and capture stderr (where silence info is printed)
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse output for silence information
        silence_periods = []
        lines = result.stderr.split('\n')
        
        for i, line in enumerate(lines):
            if "silence_start" in line:
                start_time = float(line.split("silence_start: ")[1].strip())
                
                # Find the corresponding end time
                for j in range(i, min(i + 10, len(lines))):
                    if "silence_end" in lines[j]:
                        parts = lines[j].split("silence_end: ")[1].split(" ")
                        end_time = float(parts[0])
                        silence_periods.append((start_time, end_time))
                        break
        
        return silence_periods
        
    except subprocess.CalledProcessError as e:
        print(f"Error detecting silence: {str(e)}")
        return []
    except Exception as e:
        print(f"Error detecting silence: {str(e)}")
        return []


def create_smart_chunks(
    audio_path: str,
    output_dir: str,
    job_id: str,
    target_duration: int = 30 * 60,  # 30 minutes
    overlap: int = 5,  # 5 seconds
    format: str = "wav",
) -> List[Dict[str, Any]]:
    """
    Create chunks based on natural breaks (silence) in the audio.

    Args:
        audio_path (str): Path to the audio file
        output_dir (str): Directory to save the chunks
        job_id (str): Job ID for tracking
        target_duration (int, optional): Target duration of each chunk in seconds. Defaults to 30*60 (30 minutes).
        overlap (int, optional): Overlap between chunks in seconds. Defaults to 5.
        format (str, optional): Output audio format. Defaults to "wav".

    Returns:
        List[Dict[str, Any]]: List of chunk metadata
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Get audio duration
    duration = get_audio_duration(audio_path)
    if not duration:
        update_job_step(job_id, "transcription", "failed", {"error": "Could not determine audio duration"})
        return []
    
    # Detect silence periods
    silence_periods = detect_silence(audio_path)
    
    # Create chunks based on silence and target duration
    chunks = []
    chunk_points = [0]  # Start with beginning of file
    
    current_pos = 0
    current_target = target_duration
    
    # Find natural break points close to target durations
    while current_pos < duration:
        best_break = None
        min_distance = float('inf')
        
        for start, end in silence_periods:
            if start > current_pos and abs(start - (current_pos + current_target)) < min_distance:
                min_distance = abs(start - (current_pos + current_target))
                best_break = start
        
        # If no suitable break found, just use the target duration
        if best_break is None or min_distance > target_duration * 0.2:  # Allow 20% deviation
            next_point = current_pos + target_duration
        else:
            next_point = best_break
        
        # Don't exceed file duration
        if next_point > duration:
            next_point = duration
        
        chunk_points.append(next_point)
        current_pos = next_point
        
    # Create the actual chunks
    for i in range(len(chunk_points) - 1):
        # Get start and end times with overlap
        start_time = max(0, chunk_points[i] - overlap if i > 0 else 0)
        end_time = min(duration, chunk_points[i+1] + overlap if i < len(chunk_points) - 2 else duration)
        
        # Generate chunk ID and filename
        chunk_id = f"{job_id}_chunk_{i+1:03d}"
        chunk_filename = f"{os.path.splitext(os.path.basename(audio_path))[0]}_chunk_{i+1:03d}.{format}"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        # Create the chunk
        if create_audio_chunk(audio_path, chunk_path, start_time, end_time):
            # Create chunk metadata
            chunk_data = {
                "id": chunk_id,
                "path": chunk_path,
                "start_time": int(start_time * 1000),  # Convert to milliseconds
                "end_time": int(end_time * 1000),      # Convert to milliseconds
                "sequence": i + 1
            }
            
            # Add chunk to job state
            add_chunk(job_id, chunk_id, int(start_time * 1000), int(end_time * 1000))
            
            # Add to list
            chunks.append(chunk_data)
    
    # Update job status
    update_job_step(
        job_id,
        "transcription",
        "in_progress",
        {
            "message": f"Created {len(chunks)} audio chunks using smart chunking",
            "chunks_created": len(chunks)
        }
    )
    
    return chunks