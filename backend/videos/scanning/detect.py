"""Pure media-file detection used by folder selection and scanning."""

from pathlib import Path


VIDEO_EXTENSIONS = frozenset({
    '.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg',
    '.mpeg', '.ts', '.mts', '.m2ts', '.ogv', '.3gp', '.3g2', '.f4v', '.rm',
    '.rmvb', '.asf', '.vob',
})
PHOTO_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.ico',
    '.jfif', '.avif', '.heic', '.heif',
})
SKIP_DIR_NAMES = frozenset({
    '.app_data', '$RECYCLE.BIN', 'System Volume Information', '.git',
    'node_modules', '__pycache__', '@eaDir',
})


def detect_file(path: str) -> str | None:
    """Return ``video`` or ``photo`` for a supported path, otherwise ``None``."""
    extension = Path(path).suffix.lower()
    if extension in VIDEO_EXTENSIONS:
        return 'video'
    if extension in PHOTO_EXTENSIONS:
        return 'photo'
    return None
