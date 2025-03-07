"""Services for the Duplicate Video Finder integration."""
from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Set

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_VIDEO_EXTENSIONS,
    DEFAULT_VIDEO_EXTENSIONS,
    DOMAIN,
    SERVICE_FIND_DUPLICATES,
)

_LOGGER = logging.getLogger(__name__)

# Directories to exclude from scanning
EXCLUDED_DIRS: Set[str] = {
    "/proc",
    "/sys",
    "/dev",
    "/run",
    "/tmp",
    "/var/run",
    "/var/lock",
    "/var/tmp",
    "/boot",
    "/root",
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/opt",
    "/snap",
    "/lost+found",
    "/.git",
    "/.github",
    "/.config",
    "/.local",
    "/.cache",
    "/.docker",
    "/.ssh",
    "/.gnupg",
    "/.aws",
    "/.azure",
    "/.google",
    "/.mozilla",
    "/.thunderbird",
    "/.config",
    "/.local",
    "/.cache",
    "/.docker",
    "/.ssh",
    "/.gnupg",
    "/.aws",
    "/.azure",
    "/.google",
    "/.mozilla",
    "/.thunderbird",
}

def calculate_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Calculate SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def is_excluded_directory(path: str) -> bool:
    """Check if a directory should be excluded from scanning."""
    # Convert to absolute path
    abs_path = os.path.abspath(path)
    
    # Check if the path starts with any excluded directory
    return any(abs_path.startswith(excluded) for excluded in EXCLUDED_DIRS)

def get_accessible_directories() -> list[str]:
    """Get a list of all accessible directories on the system."""
    accessible_dirs = []
    
    # Start from root directory
    root_dirs = ["/", "/home", "/media", "/mnt", "/storage"]
    
    for root_dir in root_dirs:
        if os.path.exists(root_dir):
            try:
                for root, dirs, _ in os.walk(root_dir):
                    # Skip excluded directories
                    dirs[:] = [d for d in dirs if not is_excluded_directory(os.path.join(root, d))]
                    accessible_dirs.append(root)
            except Exception as err:
                _LOGGER.warning("Error accessing directory %s: %s", root_dir, err)
    
    return accessible_dirs

async def find_duplicate_videos(
    hass: HomeAssistant,
    video_extensions: list[str] = DEFAULT_VIDEO_EXTENSIONS,
) -> dict[str, list[str]]:
    """Find duplicate video files in all accessible directories."""
    hash_dict: dict[str, list[str]] = {}
    accessible_dirs = get_accessible_directories()
    
    _LOGGER.info("Starting scan of %d accessible directories", len(accessible_dirs))
    
    for directory in accessible_dirs:
        try:
            for root, _, files in os.walk(directory):
                if is_excluded_directory(root):
                    continue
                    
                for filename in files:
                    if any(filename.lower().endswith(ext) for ext in video_extensions):
                        filepath = os.path.join(root, filename)
                        try:
                            file_hash = await hass.async_add_executor_job(
                                calculate_file_hash, filepath
                            )
                            if file_hash in hash_dict:
                                hash_dict[file_hash].append(filepath)
                            else:
                                hash_dict[file_hash] = [filepath]
                        except Exception as err:
                            _LOGGER.error("Error processing file %s: %s", filepath, err)
        except Exception as err:
            _LOGGER.warning("Error scanning directory %s: %s", directory, err)
            continue
    
    # Filter out unique files
    return {k: v for k, v in hash_dict.items() if len(v) > 1}

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Duplicate Video Finder integration."""
    
    async def handle_find_duplicates(call: ServiceCall) -> None:
        """Handle the find_duplicates service call."""
        video_exts = call.data.get(CONF_VIDEO_EXTENSIONS, DEFAULT_VIDEO_EXTENSIONS)
        
        _LOGGER.info("Starting duplicate video scan")
        duplicates = await find_duplicate_videos(hass, video_exts)
        
        # Store the results in hass.data for the frontend to access
        hass.data[DOMAIN]["duplicates"] = duplicates
        
        # Log the results
        _LOGGER.info("Found %d groups of duplicate files", len(duplicates))
        for file_hash, file_list in duplicates.items():
            _LOGGER.info("Found duplicate files with hash %s:", file_hash)
            for filepath in file_list:
                _LOGGER.info("  - %s", filepath)
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_FIND_DUPLICATES,
        handle_find_duplicates,
    ) 