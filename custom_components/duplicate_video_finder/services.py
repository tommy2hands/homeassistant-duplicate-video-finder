"""Services for the Duplicate Video Finder integration."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Set, Tuple

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
}

# Maximum number of worker threads for file hashing
MAX_WORKERS = 4

def calculate_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Calculate SHA-256 hash of a file."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except (PermissionError, FileNotFoundError, OSError) as err:
        _LOGGER.debug("Error hashing file %s: %s", filepath, err)
        return ""

def is_excluded_directory(path: str) -> bool:
    """Check if a directory should be excluded from scanning."""
    # Convert to absolute path
    abs_path = os.path.abspath(path)
    
    # Check if the path starts with any excluded directory
    return any(abs_path.startswith(excluded) for excluded in EXCLUDED_DIRS)

def get_accessible_directories() -> List[str]:
    """Get a list of all accessible directories on the system."""
    accessible_dirs = []
    
    # Start from root directory
    root_dirs = ["/", "/home", "/media", "/mnt", "/storage"]
    
    for root_dir in root_dirs:
        if os.path.exists(root_dir):
            try:
                # Only add the root directory itself, we'll walk through it later
                accessible_dirs.append(root_dir)
            except Exception as err:
                _LOGGER.warning("Error accessing directory %s: %s", root_dir, err)
    
    return accessible_dirs

def find_video_files(directory: str, video_extensions: List[str]) -> List[str]:
    """Find all video files in a directory and its subdirectories."""
    video_files = []
    
    try:
        for root, dirs, files in os.walk(directory, topdown=True):
            # Modify dirs in-place to exclude directories we don't want to scan
            dirs[:] = [d for d in dirs if not is_excluded_directory(os.path.join(root, d))]
            
            for filename in files:
                if any(filename.lower().endswith(ext) for ext in video_extensions):
                    filepath = os.path.join(root, filename)
                    video_files.append(filepath)
    except (PermissionError, OSError) as err:
        _LOGGER.warning("Error scanning directory %s: %s", directory, err)
    
    return video_files

async def hash_files_parallel(hass: HomeAssistant, files: List[str]) -> Dict[str, str]:
    """Hash multiple files in parallel using a thread pool."""
    file_hashes = {}
    
    # Use a thread pool to hash files in parallel
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Create a list of future objects
        future_to_file = {
            executor.submit(calculate_file_hash, filepath): filepath
            for filepath in files
        }
        
        # Process results as they complete
        for future in asyncio.as_completed([future for future in future_to_file]):
            filepath = future_to_file[future]
            try:
                file_hash = future.result()
                if file_hash:  # Only add if hash was successful
                    file_hashes[filepath] = file_hash
            except Exception as exc:
                _LOGGER.error("Error processing file %s: %s", filepath, exc)
    
    return file_hashes

async def find_duplicate_videos(
    hass: HomeAssistant,
    video_extensions: List[str] = DEFAULT_VIDEO_EXTENSIONS,
) -> Dict[str, List[str]]:
    """Find duplicate video files in all accessible directories."""
    start_time = time.time()
    hash_dict: Dict[str, List[str]] = {}
    accessible_dirs = get_accessible_directories()
    
    _LOGGER.info("Starting scan of %d accessible directories", len(accessible_dirs))
    
    # First, find all video files
    all_video_files = []
    for directory in accessible_dirs:
        video_files = await hass.async_add_executor_job(
            find_video_files, directory, video_extensions
        )
        all_video_files.extend(video_files)
    
    _LOGGER.info("Found %d video files to analyze", len(all_video_files))
    
    # Then, hash all files in parallel
    file_hashes = await hash_files_parallel(hass, all_video_files)
    
    # Group files by hash
    for filepath, file_hash in file_hashes.items():
        if file_hash in hash_dict:
            hash_dict[file_hash].append(filepath)
        else:
            hash_dict[file_hash] = [filepath]
    
    # Filter out unique files
    duplicates = {k: v for k, v in hash_dict.items() if len(v) > 1}
    
    elapsed_time = time.time() - start_time
    _LOGGER.info(
        "Scan completed in %.2f seconds. Found %d groups of duplicate files",
        elapsed_time,
        len(duplicates)
    )
    
    return duplicates

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Duplicate Video Finder integration."""
    # Initialize the data dictionary
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["duplicates"] = {}
    
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