videoinsight/                   # Main package directory
├── __init__.py                 # Make package importable
├── cli/                        # CLI interface
│   ├── __init__.py
│   ├── commands.py             # CLI command definitions
│   └── config.py               # Configuration handling
├── core/                       # Core functionality
│   ├── __init__.py
│   ├── downloader.py           # Video downloading
│   ├── transcription.py        # Speech-to-text
│   ├── analysis.py             # Content analysis
│   └── markdown.py             # Markdown generation
├── utils/                      # Utility functions
│   ├── __init__.py
│   ├── chunking.py             # Audio chunking
│   ├── state.py                # State persistence
│   └── helpers.py              # Misc helpers
├── models/                     # Data models
│   ├── __init__.py
│   ├── job.py                  # Job tracking models
│   └── content.py              # Content data models
├── config/                     # Configuration
│   ├── __init__.py
│   └── default.yaml            # Default configuration
├── tests/                      # Test directory
│   ├── __init__.py
│   ├── test_downloader.py
│   ├── test_transcription.py
│   └── test_analysis.py
├── scripts/                    # Utility scripts
│   └── install_models.py       # Model download script
├── docker/                     # Docker configuration
│   ├── Dockerfile
│   └── docker-compose.yml
└── k8s/                        # Kubernetes manifests (future)
    └── dev/                    # Development environment