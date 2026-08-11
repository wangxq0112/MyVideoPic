"""Read-only ffprobe metadata extraction for videos."""

import json
import os
import shutil
import subprocess


_SUBPROCESS_FLAGS: dict[str, int] = {}
if os.name == 'nt':
    _SUBPROCESS_FLAGS['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def ffmpeg_available() -> dict[str, bool]:
    """Report optional local ffmpeg binaries without invoking the network."""
    return {
        'ffmpeg': shutil.which('ffmpeg') is not None,
        'ffprobe': shutil.which('ffprobe') is not None,
    }


def extract_video_metadata(path: str) -> dict | None:
    """Return ffprobe JSON for ``path`` or ``None`` when it cannot be read."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', '-show_streams', path],
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8',
            errors='replace',
            **_SUBPROCESS_FLAGS,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError):
        return None
