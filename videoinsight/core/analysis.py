"""
Content analysis module for VideoInsight.

This module extracts key topics, concepts, and structure from transcriptions.
"""
import re
import nltk
from typing import Dict, Any, List, Optional
from collections import Counter

from videoinsight.utils.state import update_job_step, get_job


def analyze_transcription(job_id: str) -> Dict[str, Any]:
    """
    Analyze the transcription to extract key topics, concepts, and structure.
    
    Args:
        job_id: ID of the job to analyze
        
    Returns:
        Dict containing analysis results
    """
    # Get job data with transcription
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    
    # Check if we have a merged transcription
    if not job["steps"]["analysis"]["data"] or "merged_transcription" not in job["steps"]["analysis"]["data"]:
        raise ValueError("No transcription found to analyze")
    
    # Get the transcription
    transcription = job["steps"]["analysis"]["data"]["merged_transcription"]
    
    # Update job status
    update_job_step(job_id, "analysis", "in_progress", {"message": "Starting content analysis"})
    
    # Extract key topics and concepts
    topics = extract_topics(transcription["text"])
    
    # Find potential sections based on pauses and topic shifts
    sections = segment_content(transcription["segments"])
    
    # Identify key timestamps
    key_points = identify_key_points(transcription["segments"], topics)
    
    # Generate a structured outline 
    outline = generate_outline(sections, topics)
    
    # Compile analysis results
    analysis_results = {
        "topics": topics,
        "sections": sections,
        "key_points": key_points,
        "outline": outline,
    }
    
    # Update job with analysis results
    update_job_step(job_id, "analysis", "completed", {
        "message": "Content analysis completed",
        "analysis": analysis_results
    })
    
    return analysis_results


def extract_topics(text: str, num_topics: int = 10) -> List[Dict[str, Any]]:
    """
    Extract main topics from the transcription.
    
    Simple implementation using keyword frequency and NLTK.
    For production, consider using a more sophisticated approach like LDA.
    """
    # Make sure NLTK resources are available
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords')
    
    # Tokenize and clean the text
    tokens = nltk.word_tokenize(text.lower())
    stopwords = set(nltk.corpus.stopwords.words('english'))
    
    # Filter out stopwords and short words
    keywords = [word for word in tokens if word.isalnum() and 
                word not in stopwords and len(word) > 2]
    
    # Count occurrences
    keyword_freq = Counter(keywords)
    top_keywords = keyword_freq.most_common(num_topics)
    
    # Format results
    topics = []
    for word, count in top_keywords:
        topics.append({
            "keyword": word,
            "frequency": count,
            "score": count / len(keywords) if keywords else 0
        })
    
    return topics


def segment_content(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Segment content into logical sections based on pauses and topic shifts.
    """
    sections = []
    current_section = {
        "start": segments[0]["start"] if segments else 0,
        "text": "",
        "segments": []
    }
    
    previous_end = 0
    
    for segment in segments:
        # Check if there's a significant pause (over 3 seconds)
        if previous_end > 0 and (segment["start"] - previous_end) > 3000:  # 3000ms = 3s
            # End current section
            current_section["end"] = previous_end
            sections.append(current_section)
            
            # Start new section
            current_section = {
                "start": segment["start"],
                "text": segment["text"],
                "segments": [segment]
            }
        else:
            # Add to current section
            current_section["text"] += " " + segment["text"]
            current_section["segments"].append(segment)
        
        previous_end = segment["end"]
    
    # Add the last section if not empty
    if current_section["segments"]:
        current_section["end"] = previous_end
        sections.append(current_section)
    
    return sections


def identify_key_points(segments: List[Dict[str, Any]], topics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Identify key points in the transcription based on topic keywords.
    """
    key_points = []
    keywords = [topic["keyword"] for topic in topics]
    
    for segment in segments:
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', segment["text"].lower()):
                key_points.append({
                    "timestamp": segment["start"],
                    "text": segment["text"],
                    "keyword": keyword
                })
                # Only count each segment once
                break
    
    return key_points


def generate_outline(sections: List[Dict[str, Any]], topics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a structured outline of the content.
    """
    # For simplicity, we'll use the sections as main outline points
    outline = {
        "title": "Content Outline",
        "sections": []
    }
    
    topic_keywords = set(topic["keyword"] for topic in topics[:5])  # Top 5 topics
    
    for i, section in enumerate(sections):
        # Create a title from the first sentence or the first X characters
        first_sentence = section["text"].split('.')[0]
        title = first_sentence[:50] + "..." if len(first_sentence) > 50 else first_sentence
        
        # Find key topics in this section
        section_topics = []
        for keyword in topic_keywords:
            if keyword in section["text"].lower():
                section_topics.append(keyword)
        
        outline["sections"].append({
            "number": i + 1,
            "title": title,
            "start": section["start"],
            "end": section["end"],
            "topics": section_topics
        })
    
    return outline