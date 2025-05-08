"""
Transcription engine for VideoInsight.

This module handles converting audio to text using Whisper models,
with timestamp alignment and quality assessment.
"""
import os
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import numpy as np

# Use faster-whisper if available, fall back to regular whisper
try:
    from faster_whisper import WhisperModel
    USING_FASTER_WHISPER = True
except ImportError:
    import whisper
    USING_FASTER_WHISPER = False

from videoinsight.utils.state import update_job_step, update_chunk_status, get_job


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


def load_model(model_name: str, device: str = "auto", compute_type: str = "auto") -> Any:
    """
    Load the appropriate Whisper model.

    Args:
        model_name (str): Model size (tiny, base, small, medium, large)
        device (str): Device to use (cpu, cuda, auto)
        compute_type (str): Compute type for faster-whisper (float16, float32, auto)

    Returns:
        Any: Loaded model instance
    """
    if USING_FASTER_WHISPER:
        # Check if we have enough VRAM for the model
        if device == "auto":
            import torch
            if torch.cuda.is_available():
                # Estimate required VRAM based on model size
                vram_requirements = {
                    "tiny": 1,    # ~1 GB
                    "base": 1,    # ~1 GB
                    "small": 2,   # ~2 GB
                    "medium": 5,  # ~5 GB
                    "large": 10   # ~10 GB
                }
                
                # Get available VRAM
                vram_available = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # Convert to GB
                
                # Use CPU if not enough VRAM
                if vram_requirements.get(model_name, 10) > vram_available:
                    device = "cpu"
                else:
                    device = "cuda"
        
        return WhisperModel(model_name, device=device, compute_type=compute_type)
    else:
        return whisper.load_model(model_name)


def transcribe_chunk(
    chunk_path: str,
    job_id: str,
    chunk_id: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Transcribe an audio chunk.

    Args:
        chunk_path (str): Path to the audio chunk
        job_id (str): Job ID for tracking
        chunk_id (str): Chunk ID for tracking
        config (Dict[str, Any]): Configuration dictionary

    Returns:
        Dict[str, Any]: Transcription data with timestamps
    """
    # Update chunk status
    update_chunk_status(
        job_id, 
        chunk_id, 
        "in_progress", 
        {"message": "Loading transcription model"}
    )

    # Get transcription config
    model_name = config["transcription"]["model"]
    language = config["transcription"]["language"]
    beam_size = config["transcription"]["beam_size"]
    temperature = config["transcription"]["temperature"]
    word_timestamps = config["transcription"]["word_timestamps"]
    threads = config["transcription"]["threads"]

    try:
        # Load the model
        model = load_model(model_name)
        
        # Update status
        update_chunk_status(
            job_id, 
            chunk_id, 
            "in_progress", 
            {"message": "Transcribing audio"}
        )
        
        # Transcribe audio
        if USING_FASTER_WHISPER:
            # Define parameters for faster-whisper
            segments, info = model.transcribe(
                audio=chunk_path,
                language=language,
                beam_size=beam_size,
                temperature=temperature,
                word_timestamps=word_timestamps,
                threads=threads
            )
            
            # Process the segments
            transcript_data = process_faster_whisper_result(segments, info)
        else:
            # Use regular whisper
            transcription_options = {
                "language": language,
                "beam_size": beam_size,
                "temperature": temperature,
            }
            
            result = model.transcribe(
                chunk_path, 
                **transcription_options
            )
            
            # Process the result
            transcript_data = process_whisper_result(result)
        
        # Calculate basic quality metrics
        quality_metrics = calculate_quality_metrics(transcript_data)
        transcript_data["quality"] = quality_metrics
        
        # Update chunk status
        update_chunk_status(
            job_id, 
            chunk_id, 
            "completed", 
            {
                "message": "Transcription completed",
                "transcription": transcript_data
            }
        )
        
        return transcript_data
        
    except Exception as e:
        error_message = f"Transcription error: {str(e)}"
        update_chunk_status(job_id, chunk_id, "failed", {"error": error_message})
        raise Exception(error_message)


def process_faster_whisper_result(segments, info) -> Dict[str, Any]:
    """
    Process segments from faster-whisper into a standardized format.

    Args:
        segments: Segments from faster-whisper
        info: Info dictionary from faster-whisper

    Returns:
        Dict[str, Any]: Processed transcription data
    """
    transcript_text = ""
    processed_segments = []
    
    # Convert generator to list if needed
    segments_list = list(segments)
    
    for segment in segments_list:
        # Format: {"start": float, "end": float, "text": str, "words": List[Dict]}
        seg_data = {
            "start": segment.start * 1000,  # Convert to milliseconds
            "end": segment.end * 1000,      # Convert to milliseconds
            "text": segment.text.strip(),
            "words": []
        }
        
        # Add word-level data if available
        if segment.words:
            for word in segment.words:
                seg_data["words"].append({
                    "start": word.start * 1000,  # Convert to milliseconds
                    "end": word.end * 1000,      # Convert to milliseconds
                    "word": word.word,
                    "probability": word.probability
                })
        
        processed_segments.append(seg_data)
        transcript_text += segment.text + " "
    
    return {
        "text": transcript_text.strip(),
        "segments": processed_segments,
        "language": info.language,
        "language_probability": info.language_probability
    }


def process_whisper_result(result) -> Dict[str, Any]:
    """
    Process result from regular whisper into a standardized format.

    Args:
        result: Result from whisper.transcribe()

    Returns:
        Dict[str, Any]: Processed transcription data
    """
    processed_segments = []
    
    for segment in result["segments"]:
        seg_data = {
            "start": segment["start"] * 1000,  # Convert to milliseconds
            "end": segment["end"] * 1000,      # Convert to milliseconds
            "text": segment["text"].strip(),
            "words": []
        }
        
        # Add word-level data if available
        if "words" in segment:
            for word in segment["words"]:
                seg_data["words"].append({
                    "start": word["start"] * 1000,  # Convert to milliseconds
                    "end": word["end"] * 1000,      # Convert to milliseconds
                    "word": word["word"],
                    "probability": word.get("probability", 1.0)
                })
        
        processed_segments.append(seg_data)
    
    return {
        "text": result["text"].strip(),
        "segments": processed_segments,
        "language": result.get("language"),
        "language_probability": result.get("language_probability", 1.0)
    }


def calculate_quality_metrics(transcript_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate basic quality metrics for the transcription.

    Args:
        transcript_data (Dict[str, Any]): Transcription data

    Returns:
        Dict[str, float]: Quality metrics
    """
    # Basic quality metrics
    metrics = {
        "confidence": 0.0,
        "language_confidence": transcript_data.get("language_probability", 0.0),
        "avg_word_confidence": 0.0,
        "segments": len(transcript_data["segments"]),
        "words": 0
    }
    
    # Calculate word-level confidence if available
    total_words = 0
    total_confidence = 0.0
    
    for segment in transcript_data["segments"]:
        if segment["words"]:
            for word in segment["words"]:
                if "probability" in word:
                    total_confidence += word["probability"]
                    total_words += 1
    
    if total_words > 0:
        metrics["avg_word_confidence"] = total_confidence / total_words
        metrics["words"] = total_words
    
    # Calculate overall confidence
    # For now, just use language confidence and word confidence
    metrics["confidence"] = (metrics["language_confidence"] + 
                            (metrics["avg_word_confidence"] if metrics["avg_word_confidence"] > 0 else 0.5)) / 2
    
    return metrics


def transcribe_job(job_id: str) -> Dict[str, Any]:
    """
    Transcribe all chunks for a job.

    Args:
        job_id (str): Job ID

    Returns:
        Dict[str, Any]: Job data with transcription results
    """
    from videoinsight.utils.state import get_job, update_job_step
    
    # Get job data
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Update job status
    update_job_step(job_id, "transcription", "in_progress", {"message": "Starting transcription"})
    
    config = job["config"]
    
    # Check if we have chunks to process
    if not job["chunks"]:
        raise ValueError("No chunks found for transcription. Run download step first.")
    
    # Process each chunk
    for chunk in job["chunks"]:
        chunk_id = chunk["id"]
        chunk_path = None
        
        # Get chunk path from download step data
        if job["steps"]["download"]["data"] and "chunks" in job["steps"]["download"]["data"]:
            for download_chunk in job["steps"]["download"]["data"]["chunks"]:
                if download_chunk["id"] == chunk_id:
                    chunk_path = download_chunk["path"]
                    break
        
        if not chunk_path:
            # Try to get path directly from chunk
            chunk_path = chunk.get("path")
            
            if not chunk_path:
                update_chunk_status(
                    job_id, 
                    chunk_id, 
                    "failed", 
                    {"error": "Could not find chunk path"}
                )
                continue
        
        # Skip already processed chunks unless forced
        if chunk["status"] == "completed" and "transcription" in chunk:
            continue
        
        try:
            # Transcribe the chunk
            transcription = transcribe_chunk(chunk_path, job_id, chunk_id, config)
            
            # Update chunk with transcription (handled in transcribe_chunk)
            pass
            
        except Exception as e:
            # Error is logged in transcribe_chunk
            pass
    
    # Get updated job
    job = get_job(job_id)
    
    # Check if all chunks are processed
    all_completed = all(
        chunk["status"] == "completed" 
        for chunk in job["chunks"]
    )
    
    if all_completed:
        # Update job status
        update_job_step(
            job_id, 
            "transcription", 
            "completed", 
            {"message": "Transcription completed for all chunks"}
        )
    else:
        # Check if all chunks are either completed or failed
        all_processed = all(
            chunk["status"] in ["completed", "failed"] 
            for chunk in job["chunks"]
        )
        
        if all_processed:
            # Some chunks failed
            update_job_step(
                job_id, 
                "transcription", 
                "completed_with_errors", 
                {"message": "Transcription completed with errors"}
            )
        else:
            # Not all chunks are processed
            update_job_step(
                job_id, 
                "transcription", 
                "incomplete", 
                {"message": "Transcription incomplete"}
            )
    
    # Return updated job
    return get_job(job_id)


def merge_transcriptions(job_id: str) -> Dict[str, Any]:
    """
    Merge all chunk transcriptions into a single transcription.

    Args:
        job_id (str): Job ID

    Returns:
        Dict[str, Any]: Merged transcription data
    """
    from videoinsight.utils.state import get_job, update_job_step
    
    # Get job data
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Ensure transcription step is complete
    if job["steps"]["transcription"]["status"] not in ["completed", "completed_with_errors"]:
        raise ValueError("Transcription step is not complete")
    
    # Collect all transcriptions
    transcriptions = []
    
    for chunk in sorted(job["chunks"], key=lambda x: x["start_time"]):
        if chunk["status"] == "completed" and "transcription" in chunk:
            transcriptions.append({
                "start_time": chunk["start_time"],
                "end_time": chunk["end_time"],
                "data": chunk["transcription"]
            })
    
    if not transcriptions:
        raise ValueError("No transcriptions found")
    
    # Merge transcriptions
    merged = merge_transcription_data(transcriptions, job["config"]["transcription"]["overlap"] * 1000)
    
    # Update job
    update_job_step(
        job_id, 
        "analysis", 
        "in_progress", 
        {
            "message": "Transcriptions merged",
            "merged_transcription": merged
        }
    )
    
    return merged


def merge_transcription_data(transcriptions: List[Dict[str, Any]], overlap_ms: int) -> Dict[str, Any]:
    """
    Merge multiple transcription chunks, handling overlaps.

    Args:
        transcriptions (List[Dict[str, Any]]): List of transcription chunks
        overlap_ms (int): Overlap time in milliseconds

    Returns:
        Dict[str, Any]: Merged transcription data
    """
    if not transcriptions:
        return {"text": "", "segments": []}
    
    # Sort transcriptions by start time
    sorted_transcriptions = sorted(transcriptions, key=lambda x: x["start_time"])
    
    # Initialize with first transcription
    merged_text = ""
    merged_segments = []
    
    for i, trans in enumerate(sorted_transcriptions):
        data = trans["data"]
        
        # Handle segments
        for segment in data["segments"]:
            # Adjust absolute timestamps
            absolute_start = segment["start"] + trans["start_time"]
            absolute_end = segment["end"] + trans["start_time"]
            
            # Check for overlap with previous segment
            should_add = True
            if merged_segments and i > 0:
                # Segments are from different chunks and potentially overlap
                # Simple algorithm: If the segment starts within the overlap window,
                # compare the text similarity with the last segment of the previous chunk
                prev_end = sorted_transcriptions[i-1]["end_time"]
                if absolute_start < prev_end:
                    # This segment is in the overlap zone
                    # For simplicity, we'll just take the longer segment
                    # A more sophisticated approach would use text similarity
                    last_segments = [s for s in merged_segments if s["end"] > absolute_start - 5000]
                    if last_segments:
                        # If any existing segment overlaps with this one by more than 50%, skip this one
                        for last_seg in last_segments:
                            overlap_duration = min(last_seg["end"], absolute_end) - max(last_seg["start"], absolute_start)
                            seg_duration = absolute_end - absolute_start
                            
                            if overlap_duration > 0 and overlap_duration / seg_duration > 0.5:
                                should_add = False
                                break
            
            if should_add:
                # Add the adjusted segment
                adjusted_segment = {
                    "start": absolute_start,
                    "end": absolute_end,
                    "text": segment["text"],
                    "words": []
                }
                
                # Adjust word timestamps if available
                if "words" in segment and segment["words"]:
                    for word in segment["words"]:
                        adjusted_segment["words"].append({
                            "start": word["start"] + trans["start_time"],
                            "end": word["end"] + trans["start_time"],
                            "word": word["word"],
                            "probability": word.get("probability", 1.0)
                        })
                
                merged_segments.append(adjusted_segment)
                merged_text += segment["text"] + " "
    
    # Sort merged segments by start time
    merged_segments = sorted(merged_segments, key=lambda x: x["start"])
    
    # Create merged transcription object
    merged = {
        "text": merged_text.strip(),
        "segments": merged_segments,
        "language": sorted_transcriptions[0]["data"]["language"],  # Use language from first transcription
    }
    
    return merged


def save_transcription_to_file(job_id: str, output_path: str) -> bool:
    """
    Save the merged transcription to a text file.
    
    Args:
        job_id: Job ID
        output_path: Path to save the transcript
        
    Returns:
        bool: Success status
    """
    try:
        # Get job data
        job = get_job(job_id)
        if not job:
            return False
            
        # Check if we have a merged transcription
        if (not job["steps"]["analysis"]["data"] or 
            "merged_transcription" not in job["steps"]["analysis"]["data"]):
            return False
            
        # Get the transcription
        transcription = job["steps"]["analysis"]["data"]["merged_transcription"]
        
        # Create output directory if needed
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        # Format transcript with timestamps
        formatted_text = ""
        for segment in transcription["segments"]:
            timestamp = format_timestamp(segment["start"])
            formatted_text += f"[{timestamp}] {segment['text']}\n"
        
        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(formatted_text)
            
        return True
        
    except Exception as e:
        print(f"Error saving transcription: {str(e)}")
        return False