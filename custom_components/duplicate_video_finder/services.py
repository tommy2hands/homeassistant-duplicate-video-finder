"""Services for the Duplicate Video Finder integration."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import glob
import psutil
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Set, Tuple, Optional

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_VIDEO_EXTENSIONS,
    DEFAULT_VIDEO_EXTENSIONS,
    DOMAIN,
    SERVICE_FIND_DUPLICATES,
    SERVICE_PAUSE_SCAN,
    SERVICE_RESUME_SCAN,
    SERVICE_CANCEL_SCAN,
    CONF_MAX_CPU_PERCENT,
    CONF_BATCH_SIZE,
    DEFAULT_MAX_CPU_PERCENT,
    DEFAULT_BATCH_SIZE,
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

# Global scan state
scan_state = {
    "is_scanning": False,
    "is_paused": False,
    "cancel_requested": False,
    "current_file": "",
    "total_files": 0,
    "processed_files": 0,
    "start_time": None,
    "pause_time": None,
    "total_pause_time": 0,
    "found_duplicates": {},
    "pause_event": asyncio.Event(),
}

def calculate_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Calculate SHA-256 hash of a file."""
    try:
        # Update current file in scan state
        scan_state["current_file"] = filepath
        
        sha256_hash = hashlib.sha256()
        file_size = os.path.getsize(filepath)
        processed_size = 0
        
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                # Check if pause or cancel was requested
                if scan_state["cancel_requested"]:
                    return ""
                
                if scan_state["is_paused"]:
                    # Wait until resumed
                    scan_state["pause_event"].clear()
                    scan_state["pause_time"] = time.time()
                    scan_state["pause_event"].wait()
                    # Calculate pause duration
                    if scan_state["pause_time"]:
                        scan_state["total_pause_time"] += time.time() - scan_state["pause_time"]
                        scan_state["pause_time"] = None
                
                # Check CPU usage and throttle if needed
                cpu_percent = psutil.cpu_percent(interval=0.1)
                if cpu_percent > scan_state.get("max_cpu_percent", DEFAULT_MAX_CPU_PERCENT):
                    # Sleep to reduce CPU usage
                    time.sleep(0.5)
                
                sha256_hash.update(chunk)
                processed_size += len(chunk)
                
                # Update progress
                scan_state["processed_files"] = scan_state["processed_files"] + (processed_size / file_size) / scan_state["total_files"]
        
        # Increment processed files counter
        scan_state["processed_files"] += 1 / scan_state["total_files"]
        
        return sha256_hash.hexdigest()
    except (PermissionError, FileNotFoundError, OSError) as err:
        _LOGGER.debug("Error hashing file %s: %s", filepath, err)
        # Increment processed files counter even on error
        scan_state["processed_files"] += 1 / scan_state["total_files"]
        return ""

def is_excluded_directory(path: str) -> bool:
    """Check if a directory should be excluded from scanning."""
    # Convert to absolute path
    abs_path = os.path.abspath(path)
    
    # Check if the path starts with any excluded directory
    return any(abs_path.startswith(excluded) for excluded in EXCLUDED_DIRS)

def get_home_directories() -> List[str]:
    """Get a list of all directories under /home."""
    home_dirs = []
    
    # Get all directories under /home
    try:
        # Use glob to find all directories under /home
        home_dirs = glob.glob("/home/*")
        _LOGGER.info("Found %d directories under /home", len(home_dirs))
    except Exception as err:
        _LOGGER.warning("Error accessing /home directory: %s", err)
    
    return home_dirs

def find_video_files(directory: str, video_extensions: List[str]) -> List[str]:
    """Find all video files in a directory and its subdirectories."""
    video_files = []
    
    try:
        for root, dirs, files in os.walk(directory, topdown=True):
            # Check if cancel was requested
            if scan_state["cancel_requested"]:
                return video_files
                
            # Check if pause was requested
            if scan_state["is_paused"]:
                # Wait until resumed
                scan_state["pause_event"].clear()
                scan_state["pause_time"] = time.time()
                scan_state["pause_event"].wait()
                # Calculate pause duration
                if scan_state["pause_time"]:
                    scan_state["total_pause_time"] += time.time() - scan_state["pause_time"]
                    scan_state["pause_time"] = None
            
            # Modify dirs in-place to exclude directories we don't want to scan
            dirs[:] = [d for d in dirs if not is_excluded_directory(os.path.join(root, d))]
            
            for filename in files:
                if any(filename.lower().endswith(ext) for ext in video_extensions):
                    filepath = os.path.join(root, filename)
                    video_files.append(filepath)
    except (PermissionError, OSError) as err:
        _LOGGER.warning("Error scanning directory %s: %s", directory, err)
    
    return video_files

async def hash_files_parallel(hass: HomeAssistant, files: List[str], batch_size: int = DEFAULT_BATCH_SIZE) -> Dict[str, str]:
    """Hash multiple files in parallel using a thread pool."""
    file_hashes = {}
    
    # Process files in batches to manage memory usage
    for i in range(0, len(files), batch_size):
        # Check if cancel was requested
        if scan_state["cancel_requested"]:
            return file_hashes
            
        # Process a batch of files
        batch = files[i:i+batch_size]
        _LOGGER.info("Processing batch %d/%d (%d files)", i//batch_size + 1, (len(files) + batch_size - 1)//batch_size, len(batch))
        
        # Use a thread pool to hash files in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Create a list of future objects
            future_to_file = {
                executor.submit(calculate_file_hash, filepath): filepath
                for filepath in batch
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
        
        # Check memory usage and run garbage collection if needed
        memory_percent = psutil.virtual_memory().percent
        if memory_percent > 80:  # If memory usage is above 80%
            import gc
            gc.collect()  # Run garbage collection
            await asyncio.sleep(1)  # Give system time to reclaim memory
    
    return file_hashes

async def find_duplicate_videos(
    hass: HomeAssistant,
    video_extensions: List[str] = DEFAULT_VIDEO_EXTENSIONS,
    max_cpu_percent: int = DEFAULT_MAX_CPU_PERCENT,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, List[str]]:
    """Find duplicate video files in all home directories."""
    # Initialize scan state
    scan_state["is_scanning"] = True
    scan_state["is_paused"] = False
    scan_state["cancel_requested"] = False
    scan_state["current_file"] = ""
    scan_state["total_files"] = 0
    scan_state["processed_files"] = 0
    scan_state["start_time"] = time.time()
    scan_state["pause_time"] = None
    scan_state["total_pause_time"] = 0
    scan_state["found_duplicates"] = {}
    scan_state["pause_event"] = asyncio.Event()
    scan_state["pause_event"].set()  # Not paused initially
    scan_state["max_cpu_percent"] = max_cpu_percent
    scan_state["batch_size"] = batch_size
    
    hash_dict: Dict[str, List[str]] = {}
    
    try:
        # Get all directories under /home
        home_dirs = get_home_directories()
        
        if not home_dirs:
            _LOGGER.warning("No directories found under /home")
            scan_state["is_scanning"] = False
            return {}
        
        _LOGGER.info("Starting scan of %d home directories with max CPU %d%% and batch size %d", 
                    len(home_dirs), max_cpu_percent, batch_size)
        
        # First, find all video files
        all_video_files = []
        for directory in home_dirs:
            # Check if cancel was requested
            if scan_state["cancel_requested"]:
                _LOGGER.info("Scan cancelled by user")
                scan_state["is_scanning"] = False
                return {}
                
            video_files = await hass.async_add_executor_job(
                find_video_files, directory, video_extensions
            )
            all_video_files.extend(video_files)
        
        # Update total files count
        scan_state["total_files"] = len(all_video_files)
        _LOGGER.info("Found %d video files to analyze", scan_state["total_files"])
        
        if scan_state["total_files"] == 0:
            _LOGGER.info("No video files found to analyze")
            scan_state["is_scanning"] = False
            return {}
        
        # Then, hash all files in parallel with batching
        file_hashes = await hash_files_parallel(hass, all_video_files, batch_size)
        
        # Check if cancel was requested
        if scan_state["cancel_requested"]:
            _LOGGER.info("Scan cancelled by user")
            scan_state["is_scanning"] = False
            return {}
        
        # Group files by hash
        for filepath, file_hash in file_hashes.items():
            if file_hash in hash_dict:
                hash_dict[file_hash].append(filepath)
            else:
                hash_dict[file_hash] = [filepath]
        
        # Filter out unique files
        duplicates = {k: v for k, v in hash_dict.items() if len(v) > 1}
        
        # Store duplicates in scan state
        scan_state["found_duplicates"] = duplicates
        
        # Calculate elapsed time excluding pauses
        elapsed_time = time.time() - scan_state["start_time"] - scan_state["total_pause_time"]
        _LOGGER.info(
            "Scan completed in %.2f seconds (%.2f seconds including pauses). Found %d groups of duplicate files",
            elapsed_time,
            time.time() - scan_state["start_time"],
            len(duplicates)
        )
        
        scan_state["is_scanning"] = False
        return duplicates
    except Exception as err:
        _LOGGER.error("Error during scan: %s", err)
        scan_state["is_scanning"] = False
        return {}

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Duplicate Video Finder integration."""
    # Initialize the data dictionary
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["duplicates"] = {}
    hass.data[DOMAIN]["scan_state"] = scan_state
    
    async def handle_find_duplicates(call: ServiceCall) -> None:
        """Handle the find_duplicates service call."""
        # Check if already scanning
        if scan_state["is_scanning"] and not scan_state["cancel_requested"]:
            _LOGGER.warning("A scan is already in progress. Cancel it first or wait for it to complete.")
            return
            
        video_exts = call.data.get(CONF_VIDEO_EXTENSIONS, DEFAULT_VIDEO_EXTENSIONS)
        max_cpu_percent = call.data.get(CONF_MAX_CPU_PERCENT, DEFAULT_MAX_CPU_PERCENT)
        batch_size = call.data.get(CONF_BATCH_SIZE, DEFAULT_BATCH_SIZE)
        
        _LOGGER.info("Starting duplicate video scan in /home directories")
        duplicates = await find_duplicate_videos(hass, video_exts, max_cpu_percent, batch_size)
        
        # Store the results in hass.data for the frontend to access
        hass.data[DOMAIN]["duplicates"] = duplicates
        
        # Log the results
        _LOGGER.info("Found %d groups of duplicate files", len(duplicates))
        for file_hash, file_list in duplicates.items():
            _LOGGER.info("Found duplicate files with hash %s:", file_hash)
            for filepath in file_list:
                _LOGGER.info("  - %s", filepath)
    
    async def handle_pause_scan(call: ServiceCall) -> None:
        """Handle the pause_scan service call."""
        if not scan_state["is_scanning"]:
            _LOGGER.warning("No scan is currently running")
            return
            
        if scan_state["is_paused"]:
            _LOGGER.info("Scan is already paused")
            return
            
        _LOGGER.info("Pausing scan")
        scan_state["is_paused"] = True
        scan_state["pause_time"] = time.time()
    
    async def handle_resume_scan(call: ServiceCall) -> None:
        """Handle the resume_scan service call."""
        if not scan_state["is_scanning"]:
            _LOGGER.warning("No scan is currently running")
            return
            
        if not scan_state["is_paused"]:
            _LOGGER.info("Scan is not paused")
            return
            
        _LOGGER.info("Resuming scan")
        scan_state["is_paused"] = False
        
        # Calculate pause duration
        if scan_state["pause_time"]:
            scan_state["total_pause_time"] += time.time() - scan_state["pause_time"]
            scan_state["pause_time"] = None
            
        # Set the event to resume processing
        scan_state["pause_event"].set()
    
    async def handle_cancel_scan(call: ServiceCall) -> None:
        """Handle the cancel_scan service call."""
        if not scan_state["is_scanning"]:
            _LOGGER.warning("No scan is currently running")
            return
            
        _LOGGER.info("Cancelling scan")
        scan_state["cancel_requested"] = True
        
        # If paused, resume first so it can detect the cancel
        if scan_state["is_paused"]:
            scan_state["is_paused"] = False
            scan_state["pause_event"].set()
    
    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_FIND_DUPLICATES,
        handle_find_duplicates,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_PAUSE_SCAN,
        handle_pause_scan,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESUME_SCAN,
        handle_resume_scan,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_SCAN,
        handle_cancel_scan,
    ) 