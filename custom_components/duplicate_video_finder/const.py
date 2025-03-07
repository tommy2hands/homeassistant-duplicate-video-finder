"""Constants for the Duplicate Video Finder integration."""
from typing import Final

DOMAIN: Final = "duplicate_video_finder"

# Service names
SERVICE_FIND_DUPLICATES: Final = "find_duplicates"
SERVICE_PAUSE_SCAN: Final = "pause_scan"
SERVICE_RESUME_SCAN: Final = "resume_scan"
SERVICE_CANCEL_SCAN: Final = "cancel_scan"

# Configuration keys
CONF_VIDEO_EXTENSIONS: Final = "video_extensions"
CONF_MAX_CPU_PERCENT: Final = "max_cpu_percent"
CONF_BATCH_SIZE: Final = "batch_size"

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
DEFAULT_MAX_CPU_PERCENT: Final = 70  # Default maximum CPU usage percentage
DEFAULT_BATCH_SIZE: Final = 100  # Default number of files to process in a batch 