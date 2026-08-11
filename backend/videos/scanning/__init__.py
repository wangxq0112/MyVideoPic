"""Scanning helpers with no database writes.

The scanner orchestrator imports this package for file detection, metadata
extraction, and thumbnail generation.  Keeping these operations separate
makes the scan pipeline easier to change without touching task handling.
"""

from .detect import PHOTO_EXTENSIONS, SKIP_DIR_NAMES, VIDEO_EXTENSIONS, detect_file
from .extract import extract_video_metadata, ffmpeg_available
from .thumbnail import generate_video_thumbnail, remove_thumbnail

__all__ = [
    'PHOTO_EXTENSIONS',
    'SKIP_DIR_NAMES',
    'VIDEO_EXTENSIONS',
    'detect_file',
    'extract_video_metadata',
    'ffmpeg_available',
    'generate_video_thumbnail',
    'remove_thumbnail',
]
