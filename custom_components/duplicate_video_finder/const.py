"""Constants for the Duplicate Video Finder integration."""
from typing import Final

DOMAIN: Final = "duplicate_video_finder"

# Service names
SERVICE_FIND_DUPLICATES: Final = "find_duplicates"

# Configuration keys
CONF_VIDEO_EXTENSIONS: Final = "video_extensions"

# Default values
DEFAULT_VIDEO_EXTENSIONS: Final = [
    ".mp4",
    ".avi",
    ".mkv",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
] 