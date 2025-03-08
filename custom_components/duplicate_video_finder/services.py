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

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.dispatcher import async_dispatcher_send

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
    SCAN_STATE_UPDATED,
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

# Initialize the scan state once
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
    "pause_event": None,  # Will be initialized in async_setup_services
}

@callback
def update_scan_state(hass: HomeAssistant, **kwargs) -> None:
    """Update scan state and notify listeners."""
    # Update scan state with provided values
    for key, value in kwargs.items():
        if key in scan_state:
            scan_state[key] = value
    
    # Store in hass.data for access by frontend
    if DOMAIN in hass.data:
        hass.data[DOMAIN]["scan_state"] = scan_state
    
    # Notify listeners
    async_dispatcher_send(hass, SCAN_STATE_UPDATED)
    
    # Log for debugging
    _LOGGER.debug("Scan state updated: %s", scan_state)
    
    # Force update of the sensor entity
    if DOMAIN in hass.data and "entities" in hass.data[DOMAIN]:
        for entity_id in hass.data[DOMAIN]["entities"]:
            if entity_id.startswith("sensor."):
                async_dispatcher_send(hass, f"{DOMAIN}_{entity_id}_updated")

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

def find_video_files(directory: str, video_extensions: List[str], hass: Optional[HomeAssistant] = None) -> List[str]:
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
                
                # Update state for UI
                if hass:
                    hass.add_job(update_scan_state, hass, current_file=f"Paused at: {root}")
                
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
                    
                    # Update current file for UI
                    if hass and len(video_files) % 10 == 0:  # Update every 10 files to reduce overhead
                        hass.add_job(update_scan_state, hass, current_file=filepath)
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
        
        # Update scan state
        update_scan_state(hass, current_file=f"Processing batch {i//batch_size + 1}/{(len(files) + batch_size - 1)//batch_size}")
        
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
                        
                        # Update scan state
                        update_scan_state(hass, current_file=filepath)
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
    """Find duplicate videos in home directories based on content.
    
    This function scans for video files with the specified extensions,
    calculates their hashes, and returns groups of duplicate files.
    """
    # Reset scan state
    scan_state["is_scanning"] = True
    scan_state["is_paused"] = False
    scan_state["cancel_requested"] = False
    scan_state["current_file"] = "Starting scan..."
    scan_state["start_time"] = time.time()
    scan_state["pause_time"] = None
    scan_state["total_pause_time"] = 0
    scan_state["total_files"] = 0
    scan_state["processed_files"] = 0
    scan_state["found_duplicates"] = {}
    
    # Initial update
    update_scan_state(hass)
    
    # Ensure pause event is ready
    if scan_state["pause_event"] is None:
        scan_state["pause_event"] = asyncio.Event()
        scan_state["pause_event"].set()
    
    _LOGGER.info("Starting duplicate video scan")
    
    try:
        # Find video files in home directories
        all_videos = []
        home_dirs = await hass.async_add_executor_job(get_home_directories)
        
        for home_dir in home_dirs:
            _LOGGER.info("Scanning directory: %s", home_dir)
            
            # Check if scan was cancelled
            if scan_state["cancel_requested"]:
                _LOGGER.info("Scan cancelled")
                break
                
            # Wait if paused
            await scan_state["pause_event"].wait()
            
            # Find video files
            videos = await hass.async_add_executor_job(
                find_video_files, home_dir, video_extensions, hass
            )
            
            all_videos.extend(videos)
            
            # Update total file count
            scan_state["total_files"] = len(all_videos)
            update_scan_state(hass, total_files=len(all_videos))
            
        # Check if scan was cancelled
        if scan_state["cancel_requested"]:
            scan_state["is_scanning"] = False
            update_scan_state(hass, is_scanning=False)
            return {}
            
        # Calculate file hashes and find duplicates
        _LOGGER.info("Found %d video files, hashing files...", len(all_videos))
        
        # Update the scan state
        scan_state["total_files"] = len(all_videos)
        update_scan_state(hass, total_files=len(all_videos))
        
        # Hash the files in parallel with CPU limitation
        file_hashes = {}
        duplicates = {}
        
        # Process files in batches
        total_batches = (len(all_videos) + batch_size - 1) // batch_size
        
        for batch_idx in range(total_batches):
            # Check if scan was cancelled
            if scan_state["cancel_requested"]:
                _LOGGER.info("Scan cancelled during processing")
                break
                
            # Wait if paused
            await scan_state["pause_event"].wait()
            
            # Get the current batch
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(all_videos))
            current_batch = all_videos[start_idx:end_idx]
            
            # Hash the batch of files
            _LOGGER.debug("Processing batch %d/%d (%d files)", 
                         batch_idx + 1, total_batches, len(current_batch))
            
            batch_start_time = time.time()
            
            # Process each file in the batch
            for i, file_path in enumerate(current_batch):
                # Check if scan was cancelled
                if scan_state["cancel_requested"]:
                    break
                    
                # Wait if paused
                await scan_state["pause_event"].wait()
                
                # Limit CPU usage
                while psutil.cpu_percent(interval=0.1) > max_cpu_percent:
                    if scan_state["cancel_requested"]:
                        break
                    await asyncio.sleep(0.5)
                
                # Update current file
                scan_state["current_file"] = file_path
                scan_state["processed_files"] = start_idx + i
                
                # Update at regular intervals to avoid too many updates
                if i % 5 == 0 or i == len(current_batch) - 1:
                    update_scan_state(
                        hass, 
                        current_file=file_path,
                        processed_files=start_idx + i
                    )
                
                # Calculate hash
                try:
                    file_hash = await hass.async_add_executor_job(calculate_file_hash, file_path)
                    file_hashes[file_path] = file_hash
                    
                    # Check for duplicates
                    if file_hash in duplicates:
                        duplicates[file_hash].append({
                            "path": file_path,
                            "size": os.path.getsize(file_path),
                            "created": os.path.getctime(file_path)
                        })
                    else:
                        duplicates[file_hash] = [{
                            "path": file_path,
                            "size": os.path.getsize(file_path),
                            "created": os.path.getctime(file_path)
                        }]
                except Exception as err:
                    _LOGGER.error("Error hashing file %s: %s", file_path, err)
            
            # Update processed files after batch
            scan_state["processed_files"] = end_idx
            update_scan_state(hass, processed_files=end_idx)
            
            batch_duration = time.time() - batch_start_time
            _LOGGER.debug("Batch %d/%d completed in %.2f seconds", 
                         batch_idx + 1, total_batches, batch_duration)
            
            # Update found duplicates every batch
            filtered_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
            scan_state["found_duplicates"] = filtered_duplicates
            update_scan_state(hass, found_duplicates=filtered_duplicates)
        
        # Filter to only include actual duplicates (more than 1 file with same hash)
        result_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
        
        # Final update
        scan_state["is_scanning"] = False
        scan_state["current_file"] = ""
        scan_state["found_duplicates"] = result_duplicates
        update_scan_state(
            hass,
            is_scanning=False,
            current_file="",
            found_duplicates=result_duplicates
        )
        
        _LOGGER.info("Scan completed, found %d groups of duplicates", len(result_duplicates))
        
        return result_duplicates
        
    except Exception as err:
        _LOGGER.error("Error during scan: %s", err)
        
        # Reset scan state on error
        scan_state["is_scanning"] = False
        scan_state["current_file"] = f"Error: {str(err)}"
        update_scan_state(
            hass,
            is_scanning=False,
            current_file=f"Error: {str(err)}"
        )
        
        return {}

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Duplicate Video Finder integration."""
    # Initialize the data dictionary
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["duplicates"] = {}
    hass.data[DOMAIN]["scan_state"] = scan_state
    hass.data[DOMAIN].setdefault("entities", [])
    
    # Initialize the pause event
    scan_state["pause_event"] = asyncio.Event()
    scan_state["pause_event"].set()  # Not paused initially
    
    # Make sure the initial scan state is propagated
    update_scan_state(hass)
    
    async def handle_find_duplicates(call: ServiceCall) -> None:
        """Handle the find_duplicates service call."""
        # Check if already scanning
        if scan_state["is_scanning"] and not scan_state["cancel_requested"]:
            _LOGGER.warning("A scan is already in progress. Cancel it first or wait for it to complete.")
            return
            
        video_exts = call.data.get(CONF_VIDEO_EXTENSIONS, DEFAULT_VIDEO_EXTENSIONS)
        max_cpu_percent = call.data.get(CONF_MAX_CPU_PERCENT, DEFAULT_MAX_CPU_PERCENT)
        batch_size = call.data.get(CONF_BATCH_SIZE, DEFAULT_BATCH_SIZE)
        
        # Reset scan state
        scan_state["is_scanning"] = True
        scan_state["is_paused"] = False
        scan_state["cancel_requested"] = False
        scan_state["current_file"] = "Initializing scan..."
        scan_state["processed_files"] = 0
        scan_state["total_files"] = 0
        scan_state["start_time"] = time.time()
        scan_state["pause_time"] = None
        scan_state["total_pause_time"] = 0
        
        # Update state immediately
        update_scan_state(hass)
        
        _LOGGER.info("Starting duplicate video scan in /home directories")
        
        # Run the scan in a background task to avoid blocking
        hass.async_create_task(
            find_duplicate_videos(hass, video_exts, max_cpu_percent, batch_size)
        )
    
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
        scan_state["pause_event"].clear()
        
        # Update scan state
        update_scan_state(hass, is_paused=True)
    
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
        
        # Update scan state
        update_scan_state(hass, is_paused=False)
    
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
            
        # Update scan state
        update_scan_state(hass, cancel_requested=True)
    
    # Register all services
    hass.services.async_register(
        DOMAIN, SERVICE_FIND_DUPLICATES, handle_find_duplicates
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_PAUSE_SCAN, handle_pause_scan
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_RESUME_SCAN, handle_resume_scan
    )
    
    hass.services.async_register(
        DOMAIN, SERVICE_CANCEL_SCAN, handle_cancel_scan
    )
    
    # Log all the registered services for debugging
    _LOGGER.info("Registered services: %s", hass.services.async_services().get(DOMAIN, {}))
    
    return True 