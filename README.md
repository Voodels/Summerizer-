Here's a structured README.md file for VideoInsight CLI:


# VideoInsight CLI

A command-line tool for generating comprehensive notes from YouTube videos. Transcribes audio, analyzes content, and produces structured markdown notes with key topics and timestamps.

![VideoInsight Architecture](your-architecture-image-url-here) <!-- Add image if available -->

## Features

- 🎥 YouTube video downloading using `yt-dlp` with flexible format options
- 🔊 Audio transcription using Whisper AI models (adjustable quality levels)
- 🧠 Content analysis for key topics, concepts, and structure extraction
- 📝 Markdown generation with timestamps and hierarchical organization
- 🔄 Resume interrupted processing with fault-tolerant job management
- 🔒 Local processing for privacy & no API costs

## Installation

### Prerequisites
- Python 3.10+
- FFmpeg (for audio extraction)
- Recommended: 4GB+ RAM for transcription

```bash
# Clone repository
git clone https://github.com/Voodels/Summerizer-.git
cd Summerizer-

# Install package
pip install -e .
```

## Usage

### Process a YouTube Video
```bash
videoinsight process "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --output notes.md
```

### Resume Interrupted Job
```bash
videoinsight resume 3f7a912e-c3b1-4b3a-8a6e-1f82a3e3c8d9
```

### Manage Jobs
```bash
# List all jobs
videoinsight list

# Show configuration
videoinsight config --show

# Reset configuration
videoinsight config --reset
```

## Command Options

| Option          | Short | Description                                  | Default       |
|-----------------|-------|----------------------------------------------|---------------|
| `--output`      | `-o`  | Output file path                             | `notes.md`    |
| `--quality`     | `-q`  | Transcription quality: low/medium/high       | `medium`      |
| `--detail`      | `-d`  | Note detail: summary/standard/comprehensive  | `standard`    |
| `--language`    | `-l`  | Force language (ISO code, e.g., 'en')        | Auto-detect   |
| `--force`       | `-f`  | Force reprocessing of existing files         | `False`       |

## Architecture Overview

```
videoinsight/
├── cli/               # Command-line interface
│   ├── commands.py    # CLI command definitions
│   ├── config.py      # Configuration handling
├── core/              # Core functionality
│   ├── downloader.py  # Video downloading
│   ├── transcription.py # Audio transcription
│   ├── analysis.py    # Content analysis
│   ├── markdown.py    # Markdown generation
├── utils/             # Utilities
│   ├── state.py       # Job state management
│   ├── chunking.py    # Audio chunking
```

### Processing Workflow
1. **CLI Parsing**: `commands.py` handles user arguments
2. **Job Creation**: Unique ID generation with `state.py`
3. **Video Download**: `downloader.py` fetches video using yt-dlp
4. **Audio Processing**:
   - Extract audio from video
   - Split into chunks with smart overlap
5. **Transcription**: Parallel Whisper model processing
6. **Content Analysis**:
   - Topic extraction (keywords/frequency)
   - Content segmentation
   - Outline generation
7. **Markdown Generation**: Structured note creation

## Core Modules

### 1. Downloader
- YouTube video download via yt-dlp
- Metadata extraction

### 2. Transcription
- Whisper model integration
- Audio chunk processing

### 3. Analysis
- Key topic identification
- Content structure detection

### 4. Markdown Generator
- Timestamp integration
- Hierarchical formatting

## Example Output

Generated notes include:
- Video metadata (title, duration, source)
- Frequency-based key topics
- Timestamped content outline
- Detailed segment breakdowns
- Visual hierarchy for easy navigation

```markdown
## Key Topics

1. Machine Learning (12 mentions)
2. Neural Networks (9 mentions)
3. Data Processing (7 mentions)

### Content Outline
00:00-05:25 - Introduction to AI
  - Historical context
  - Basic concepts
05:26-12:40 - Machine Learning Fundamentals
  - Supervised vs unsupervised learning
  - ...
```

## Limitations

- Long videos (>2 hours) may require significant memory
- Transcription quality depends on audio clarity
- Currently YouTube-exclusive support

## License
MIT License - See [LICENSE](LICENSE) file

## Contributing
Contributions welcome! Please submit PRs with:
- Detailed description of changes
- Updated tests (if applicable)
- Relevant documentation updates
```

T