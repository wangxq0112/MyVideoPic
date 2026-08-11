"""Application services shared by API views.

These functions are used by API views but do not depend on HTTP request or
response objects. They never modify files selected as media sources.
"""

import os

from .scanning.detect import SKIP_DIR_NAMES, detect_file


def detect_library_media_types(folder_path: str) -> dict[str, int]:
    """Recursively count recognized files in a user-selected directory."""
    counts = {'video': 0, 'photo': 0}
    for root, directories, filenames in os.walk(folder_path):
        directories[:] = [
            name for name in directories
            if name not in SKIP_DIR_NAMES and not name.startswith('.')
        ]
        for filename in filenames:
            if filename.startswith('.'):
                continue
            media_type = detect_file(filename)
            if media_type:
                counts[media_type] += 1
    return counts
