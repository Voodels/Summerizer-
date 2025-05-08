"""
State management for VideoInsight.

This module handles job tracking, persistence, and retrieval,
enabling fault-tolerant processing of long videos.
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid
import shutil

# Define the jobs directory
JOBS_DIR = os.path.join(os.path.expanduser("~"), ".videoinsight", "jobs")

# Ensure jobs directory exists
os.makedirs(JOBS_DIR, exist_ok=True)

def create_job(job_id: str, url: str, output_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a new job and persist its state.

    Args:
        job_id (str): Unique identifier for the job
        url (str): YouTube video URL
        output_path (str): Path where the output will be saved
        config (Dict[str, Any]): Configuration for the job

    Returns:
        Dict[str, Any]: Job information
    """
    # Create job data structure
    job_data = {
        "id": job_id,
        "url": url,
        "output_path": output_path,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "config": config,
        "steps": {
            "download": {"status": "pending", "start_time": None, "end_time": None, "data": None},
            "transcription": {"status": "pending", "start_time": None, "end_time": None, "data": None},
            "analysis": {"status": "pending", "start_time": None, "end_time": None, "data": None},
            "markdown": {"status": "pending", "start_time": None, "end_time": None, "data": None},
        },
        "chunks": [],
    }

    # Save job state
    save_job(job_data)
    return job_data

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a job by its ID.

    Args:
        job_id (str): The job ID

    Returns:
        Optional[Dict[str, Any]]: Job data or None if not found
    """
    job_path = os.path.join(JOBS_DIR, f"{job_id}.json")
    
    if not os.path.exists(job_path):
        return None
    
    try:
        with open(job_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading job {job_id}: {str(e)}")
        return None

def list_jobs() -> List[Dict[str, Any]]:
    """
    List all jobs.

    Returns:
        List[Dict[str, Any]]: List of job metadata
    """
    jobs = []
    
    # Check if jobs directory exists
    if not os.path.exists(JOBS_DIR):
        return jobs
    
    # List all job files
    for filename in os.listdir(JOBS_DIR):
        if filename.endswith(".json"):
            job_id = filename.replace(".json", "")
            job = get_job(job_id)
            if job:
                # Add a simplified version of the job to the list
                jobs.append({
                    "id": job["id"],
                    "url": job["url"],
                    "status": job["status"],
                    "created_at": job["created_at"],
                    "updated_at": job["updated_at"],
                    "output_path": job["output_path"]
                })
    
    # Sort jobs by creation date (newest first)
    jobs.sort(key=lambda j: j["created_at"], reverse=True)
    return jobs

def update_job_status(job_id: str, status: str) -> Optional[Dict[str, Any]]:
    """
    Update the status of a job.

    Args:
        job_id (str): The job ID
        status (str): New status value

    Returns:
        Optional[Dict[str, Any]]: Updated job data or None if failed
    """
    job = get_job(job_id)
    if not job:
        return None
    
    job["status"] = status
    job["updated_at"] = datetime.now().isoformat()
    
    save_job(job)
    return job

def update_job_step(job_id: str, step: str, status: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Update the status and data for a specific job step.

    Args:
        job_id (str): The job ID
        step (str): Step name (e.g., "download", "transcription")
        status (str): New status for the step
        data (Optional[Dict[str, Any]], optional): Step-specific data. Defaults to None.

    Returns:
        Optional[Dict[str, Any]]: Updated job data or None if failed
    """
    job = get_job(job_id)
    if not job or step not in job["steps"]:
        return None
    
    # Update the step
    job["steps"][step]["status"] = status
    job["updated_at"] = datetime.now().isoformat()
    
    # Set start/end time based on status
    if status == "in_progress" and not job["steps"][step]["start_time"]:
        job["steps"][step]["start_time"] = datetime.now().isoformat()
    elif status in ["completed", "failed"] and not job["steps"][step]["end_time"]:
        job["steps"][step]["end_time"] = datetime.now().isoformat()
    
    # Update step data if provided
    if data:
        if not job["steps"][step]["data"]:
            job["steps"][step]["data"] = {}
        job["steps"][step]["data"].update(data)
    
    # Update overall job status based on step
    if step == "markdown" and status == "completed":
        job["status"] = "completed"
    elif status == "in_progress" and job["status"] == "created":
        job["status"] = "in_progress"
    elif status == "failed":
        job["status"] = "failed"
    
    save_job(job)
    return job

def add_chunk(job_id: str, chunk_id: str, start_time: int, end_time: int) -> Optional[Dict[str, Any]]:
    """
    Add a new processing chunk to a job.

    Args:
        job_id (str): The job ID
        chunk_id (str): Unique identifier for the chunk
        start_time (int): Start time in milliseconds
        end_time (int): End time in milliseconds

    Returns:
        Optional[Dict[str, Any]]: Updated job data or None if failed
    """
    job = get_job(job_id)
    if not job:
        return None
    
    # Create chunk data
    chunk = {
        "id": chunk_id,
        "start_time": start_time,
        "end_time": end_time,
        "status": "created",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "transcription": None,
        "analysis": None
    }
    
    job["chunks"].append(chunk)
    job["updated_at"] = datetime.now().isoformat()
    
    save_job(job)
    return job

def update_chunk_status(job_id: str, chunk_id: str, status: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Update the status and data for a specific chunk.

    Args:
        job_id (str): The job ID
        chunk_id (str): The chunk ID
        status (str): New status for the chunk
        data (Optional[Dict[str, Any]], optional): Chunk-specific data. Defaults to None.

    Returns:
        Optional[Dict[str, Any]]: Updated job data or None if failed
    """
    job = get_job(job_id)
    if not job:
        return None
    
    # Find the chunk
    chunk_idx = None
    for idx, chunk in enumerate(job["chunks"]):
        if chunk["id"] == chunk_id:
            chunk_idx = idx
            break
    
    if chunk_idx is None:
        return None
    
    # Update chunk
    job["chunks"][chunk_idx]["status"] = status
    job["chunks"][chunk_idx]["updated_at"] = datetime.now().isoformat()
    
    # Update data if provided
    if data:
        for key, value in data.items():
            job["chunks"][chunk_idx][key] = value
    
    job["updated_at"] = datetime.now().isoformat()
    
    save_job(job)
    return job

def save_job(job: Dict[str, Any]) -> None:
    """
    Save job state to disk with atomic write operation.

    Args:
        job (Dict[str, Any]): Job data to save
    """
    job_path = os.path.join(JOBS_DIR, f"{job['id']}.json")
    temp_path = os.path.join(JOBS_DIR, f"{job['id']}.tmp.json")
    
    try:
        # Write to temporary file first
        with open(temp_path, "w") as f:
            json.dump(job, f, indent=2)
        
        # Atomically replace the original file
        shutil.move(temp_path, job_path)
    except Exception as e:
        print(f"Error saving job {job['id']}: {str(e)}")
        # Clean up temp file if it exists
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

def delete_job(job_id: str) -> bool:
    """
    Delete a job and its state.

    Args:
        job_id (str): The job ID to delete

    Returns:
        bool: True if deleted successfully, False otherwise
    """
    job_path = os.path.join(JOBS_DIR, f"{job_id}.json")
    
    if not os.path.exists(job_path):
        return False
    
    try:
        os.remove(job_path)
        return True
    except Exception as e:
        print(f"Error deleting job {job_id}: {str(e)}")
        return False

def get_job_status(job_id: str) -> Optional[str]:
    """
    Get the current status of a job.

    Args:
        job_id (str): The job ID

    Returns:
        Optional[str]: Current job status or None if job not found
    """
    job = get_job(job_id)
    if job:
        return job["status"]
    return None