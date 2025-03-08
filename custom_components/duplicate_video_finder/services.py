"""Services for the Duplicate Video Finder integration."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import glob
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Set, Tuple, Optional
from pathlib import Path
import shutil

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
    SCAN_STATE_ENTITY_ID,
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
    
    # Log for debugging
    _LOGGER.debug("Scan state updated: %s", {k: v for k, v in scan_state.items() 
                                            if k != 'found_duplicates'})
    
    # Force a state update regardless of entity status
    entity_state_name = "scanning"
    if not scan_state.get("is_scanning", False):
        entity_state_name = "idle"
    elif scan_state.get("is_paused", False):
        entity_state_name = "paused"
        
    # Calculate progress
    processed = scan_state.get("processed_files", 0)
    total = max(scan_state.get("total_files", 1), 1)
    progress = round((processed / total) * 100, 1) if total > 0 else 0
    
    # Directly set the entity state
    hass.states.async_set(
        SCAN_STATE_ENTITY_ID,
        entity_state_name,
        {
            "progress": progress,
            "current_file": scan_state.get("current_file", ""),
            "total_files": scan_state.get("total_files", 0),
            "processed_files": scan_state.get("processed_files", 0),
            "friendly_name": "Duplicate Video Finder Scan State",
        }
    )
    
    # Notify listeners for components using dispatcher
    async_dispatcher_send(hass, SCAN_STATE_UPDATED)

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
                    
                    # Update scan state
                    update_scan_state(hass, current_file=filepath)
            except Exception as exc:
                _LOGGER.error("Error processing file %s: %s", filepath, exc)
    
    return file_hashes

async def find_duplicate_videos(
    hass: HomeAssistant,
    video_extensions: List[str] = DEFAULT_VIDEO_EXTENSIONS,
) -> Dict[str, List[str]]:
    """Find duplicate videos in home directories based on content."""
    _LOGGER.debug("Starting find_duplicate_videos with extensions: %s", video_extensions)
    
    # Make sure scan state is marked as scanning before we start
    update_scan_state(hass, 
        is_scanning=True,
        current_file="Starting scan...",
        processed_files=0,
        total_files=0
    )
    
    # Ensure pause event is ready
    if scan_state["pause_event"] is None:
        scan_state["pause_event"] = asyncio.Event()
        scan_state["pause_event"].set()
    
    _LOGGER.info("Starting duplicate video scan")
    
    try:
        # Find video files in home directories
        all_videos = []
        home_dirs = await hass.async_add_executor_job(get_home_directories)
        _LOGGER.debug("Found home directories: %s", home_dirs)
        
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
            _LOGGER.debug("Found %d videos in %s", len(videos), home_dir)
            
            all_videos.extend(videos)
            
            # Update total file count
            scan_state["total_files"] = len(all_videos)
            update_scan_state(hass, 
                total_files=len(all_videos),
                current_file=f"Found {len(all_videos)} video files so far..."
            )
            
        # Check if scan was cancelled
        if scan_state["cancel_requested"]:
            _LOGGER.info("Scan cancelled after finding files")
            update_scan_state(hass, is_scanning=False)
            return {}
            
        # Calculate file hashes and find duplicates
        _LOGGER.info("Found %d video files, starting to hash files...", len(all_videos))
        
        # Update the scan state
        update_scan_state(hass, 
            total_files=len(all_videos),
            current_file=f"Starting to hash {len(all_videos)} files..."
        )
        
        # Make sure we're still in scanning state before proceeding
        if not scan_state["is_scanning"]:
            _LOGGER.debug("Resetting scanning state to True")
            update_scan_state(hass, is_scanning=True)
        
        # Process files
        duplicates = {}
        
        # Hash all files in parallel
        _LOGGER.debug("Starting parallel file hashing")
        file_hashes = await hash_files_parallel(hass, all_videos)
        _LOGGER.debug("Completed hashing %d files", len(file_hashes))
        
        # Group files by hash to find duplicates
        for filepath, file_hash in file_hashes.items():
            if file_hash in duplicates:
                duplicates[file_hash].append({
                    "path": filepath,
                    "size": os.path.getsize(filepath),
                    "created": os.path.getctime(filepath)
                })
            else:
                duplicates[file_hash] = [{
                    "path": filepath,
                    "size": os.path.getsize(filepath),
                    "created": os.path.getctime(filepath)
                }]
        
        # Filter to only include actual duplicates (more than 1 file with same hash)
        result_duplicates = {k: v for k, v in duplicates.items() if len(v) > 1}
        
        _LOGGER.debug("Found %d groups of duplicates", len(result_duplicates))
        
        # Final update
        scan_state["found_duplicates"] = result_duplicates
        update_scan_state(
            hass,
            is_scanning=False,  # Explicitly set to false when complete
            current_file="Scan complete!",
            found_duplicates=result_duplicates
        )
        
        _LOGGER.info("Scan completed, found %d groups of duplicates", len(result_duplicates))
        
        return result_duplicates
        
    except Exception as err:
        _LOGGER.error("Error during scan: %s", err, exc_info=True)  # Added exc_info for full traceback
        update_scan_state(
            hass,
            is_scanning=False,  # Explicitly set to false on error
            current_file=f"Error: {str(err)}"
        )
        raise

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
            
        # Get scan parameters
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
        scan_state["found_duplicates"] = {}
        
        # Update state immediately - this ensures the entity reflects our scanning state
        update_scan_state(hass)
        
        _LOGGER.info("Starting duplicate video scan in /home directories")
        
        # Run the scan in a background task
        async def run_scan():
            try:
                # Store the task reference to prevent premature garbage collection
                hass.data[DOMAIN]["scan_task"] = asyncio.current_task()
                
                # This needs to be in a try/except to ensure scanning state is reset on error
                duplicates = await find_duplicate_videos(hass, video_exts)
                
                # Update found duplicates
                scan_state["found_duplicates"] = duplicates
                
            except Exception as err:
                _LOGGER.error("Error during scan: %s", err)
                # Reset scan state on error
                scan_state["is_scanning"] = False
                scan_state["current_file"] = f"Error: {str(err)}"
                update_scan_state(hass)
            finally:
                # Only reset scanning state if we're the current scan task
                current_task = hass.data[DOMAIN].get("scan_task")
                if current_task == asyncio.current_task():
                    scan_state["is_scanning"] = False
                    if not scan_state.get("cancel_requested"):
                        scan_state["current_file"] = "Scan complete!"
                    update_scan_state(hass)
                    # Clear the task reference
                    hass.data[DOMAIN]["scan_task"] = None
        
        # Start the scan in the background and store the task
        hass.async_create_task(run_scan())
    
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
    
    async def handle_create_test_files(call: ServiceCall) -> None:
        """Handle the create_test_files service call."""
        try:
            # Create test directory in config directory
            config_dir = hass.config.config_dir
            test_dir = os.path.join(config_dir, "duplicate_video_finder_test")
            os.makedirs(test_dir, exist_ok=True)

            # Create a small test video file
            test_content = b"This is a test video file content"
            original_path = os.path.join(test_dir, "original_test.mp4")
            duplicate_path = os.path.join(test_dir, "duplicate_test.mp4")

            # Write the original file
            with open(original_path, "wb") as f:
                f.write(test_content)

            # Create the duplicate by copying
            shutil.copy2(original_path, duplicate_path)

            _LOGGER.info("Created test files at: %s", test_dir)

            # Update the scan state to show the test files
            scan_state["found_duplicates"] = {
                hashlib.sha256(test_content).hexdigest(): [
                    {
                        "path": original_path,
                        "size": len(test_content),
                        "created": os.path.getctime(original_path)
                    },
                    {
                        "path": duplicate_path,
                        "size": len(test_content),
                        "created": os.path.getctime(duplicate_path)
                    }
                ]
            }
            update_scan_state(hass)

        except Exception as err:
            _LOGGER.error("Error creating test files: %s", err)
            raise

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

    hass.services.async_register(
        DOMAIN, "create_test_files", handle_create_test_files
    )
    
    # Log all the registered services for debugging
    _LOGGER.info("Registered services: %s", hass.services.async_services().get(DOMAIN, {}))
    
    return True 