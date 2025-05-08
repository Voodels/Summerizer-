from setuptools import setup, find_packages

setup(
    name="videoinsight",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "typer>=0.9.0",
        "yt-dlp>=2023.3.4",
        "faster-whisper>=0.6.0",
        "spacy>=3.5.3",
        "pydantic>=2.0.0",
        "rich>=13.3.5",
        "pyyaml>=6.0",
        "tqdm>=4.65.0",
        "sentence-transformers>=2.2.2",
        "keybert>=0.7.0",
        "numpy>=1.24.3",
        "pandas>=2.0.1",
        "prefect>=2.10.18",
        "SQLAlchemy>=2.0.15",
    ],
    entry_points={
        'console_scripts': [
            'videoinsight=videoinsight.cli.commands:app',
        ],
    },
    python_requires=">=3.10",
    author="Vighnesh",
    author_email="your.email@example.com",
    description="CLI tool for generating comprehensive notes from YouTube videos",
    keywords="youtube, transcription, notes, markdown, ai",
    project_urls={
        "Source Code": "https://github.com/Voodels/Summerizer-",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Education",
        "Topic :: Multimedia :: Video",
        "Programming Language :: Python :: 3.10",
    ],
)
