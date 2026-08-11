"""Thumbnail cache helpers.  They write only to the application data folder."""

import os
import subprocess
from pathlib import Path

from django.conf import settings

from .extract import _SUBPROCESS_FLAGS


def generate_video_thumbnail(path: str, media_id: str, duration: float | None) -> str:
    """Capture one video frame into the UUID-named thumbnail cache."""
    thumbnail_dir = Path(settings.APP_DATA_DIR)
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_path = thumbnail_dir / f'{media_id}_thumb.jpg'
    seek = min(max(duration * 0.1, 1.0), max(duration - 0.5, 0.0)) if duration else 1.0

    try:
        subprocess.run(
            ['ffmpeg', '-y', '-v', 'quiet', '-ss', f'{seek:.3f}', '-i', path,
             '-vframes', '1', '-vf', 'scale=480:-2:force_original_aspect_ratio=decrease',
             '-q:v', '4', str(thumbnail_path)],
            check=True,
            timeout=60,
            capture_output=True,
            **_SUBPROCESS_FLAGS,
        )
        if thumbnail_path.is_file() and thumbnail_path.stat().st_size > 0:
            return str(thumbnail_path)
    except (subprocess.SubprocessError, OSError):
        pass

    try:
        thumbnail_path.unlink(missing_ok=True)
    except OSError:
        pass
    return ''


def remove_thumbnail(path: str) -> None:
    """Best-effort removal of a cached thumbnail, never an original media file."""
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass
