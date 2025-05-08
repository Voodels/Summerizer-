# Summerizer-
a tool for heavy yt videos to notes making 


VideoInsight CLI
A fault-tolerant CLI tool for generating comprehensive markdown notes from long YouTube videos.
Features

Download and process YouTube videos up to 12+ hours in length
Generate structured, hierarchical markdown notes
Extract key concepts and topics with timestamps
Process videos in chunks with fault tolerance
Local processing for privacy

Installation
Prerequisites

Python 3.10+
ffmpeg

Install from source
bash# Clone the repository
git clone https://github.com/yourusername/videoinsight.git
cd videoinsight

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the package in development mode
pip install -e .
Quick Start
bash# Process a YouTube video and generate notes
videoinsight process https://www.youtube.com/watch?v=VIDEO_ID

# Resume a previously interrupted job
videoinsight resume JOB_ID

# Configure default settings
videoinsight config
Advanced Usage
bash# Specify output file
videoinsight process https://www.youtube.com/watch?v=VIDEO_ID --output notes.md

# Set transcription quality
videoinsight process https://www.youtube.com/watch?v=VIDEO_ID --quality high

# Set detail level for notes
videoinsight process https://www.youtube.com/watch?v=VIDEO_ID --detail comprehensive
Development
bash# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black videoinsight tests
isort videoinsight tests
License
MIT