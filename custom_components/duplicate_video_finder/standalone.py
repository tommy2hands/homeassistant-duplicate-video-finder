"""Standalone script for finding duplicate videos."""
import os
import hashlib
import argparse
import json
from typing import Dict, List, Set

def calculate_file_hash(filepath: str, chunk_size: int = 8192) -> str:
    """Calculate SHA-256 hash of a file."""
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    except Exception as err:
        print(f"Error hashing file {filepath}: {err}")
        return ""

def is_excluded_directory(path: str, excluded_dirs: Set[str]) -> bool:
    """Check if a directory should be excluded from scanning."""
    # Convert to absolute path
    abs_path = os.path.abspath(path)
    
    # Check if the path starts with any excluded directory
    return any(abs_path.startswith(excluded) for excluded in excluded_dirs)

def find_video_files(directory: str, video_extensions: List[str], excluded_dirs: Set[str]) -> List[str]:
    """Find all video files in a directory and its subdirectories."""
    video_files = []
    
    try:
        for root, dirs, files in os.walk(directory, topdown=True):
            # Modify dirs in-place to exclude directories we don't want to scan
            dirs[:] = [d for d in dirs if not is_excluded_directory(os.path.join(root, d), excluded_dirs)]
            
            for filename in files:
                if any(filename.lower().endswith(ext) for ext in video_extensions):
                    filepath = os.path.join(root, filename)
                    video_files.append(filepath)
    except Exception as err:
        print(f"Error scanning directory {directory}: {err}")
    
    return video_files

def find_duplicate_videos(
    scan_directories: List[str],
    video_extensions: List[str],
    excluded_dirs: Set[str]
) -> Dict[str, List[str]]:
    """Find duplicate video files in the specified directories."""
    hash_dict: Dict[str, List[str]] = {}
    
    # First, find all video files
    all_video_files = []
    for directory in scan_directories:
        if not os.path.exists(directory):
            print(f"Directory {directory} does not exist")
            continue
            
        video_files = find_video_files(directory, video_extensions, excluded_dirs)
        all_video_files.extend(video_files)
    
    print(f"Found {len(all_video_files)} video files to analyze")
    
    # Then, hash all files
    for filepath in all_video_files:
        file_hash = calculate_file_hash(filepath)
        if file_hash:
            if file_hash in hash_dict:
                hash_dict[file_hash].append(filepath)
            else:
                hash_dict[file_hash] = [filepath]
    
    # Filter out unique files
    duplicates = {k: v for k, v in hash_dict.items() if len(v) > 1}
    
    print(f"Found {len(duplicates)} groups of duplicate files")
    
    return duplicates

def main():
    """Run the standalone duplicate video finder."""
    parser = argparse.ArgumentParser(description="Find duplicate video files")
    parser.add_argument("--directories", "-d", nargs="+", required=True, help="Directories to scan")
    parser.add_argument("--extensions", "-e", nargs="+", default=[".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"], help="Video file extensions to scan for")
    parser.add_argument("--output", "-o", default="duplicates.json", help="Output file for results")
    args = parser.parse_args()
    
    # Default excluded directories
    excluded_dirs = {
        "/proc", "/sys", "/dev", "/run", "/tmp", "/var/run", "/var/lock",
        "/var/tmp", "/boot", "/root", "/etc", "/usr", "/bin", "/sbin",
        "/lib", "/lib64", "/opt", "/snap", "/lost+found"
    }
    
    print(f"Scanning directories: {args.directories}")
    print(f"Looking for extensions: {args.extensions}")
    
    duplicates = find_duplicate_videos(args.directories, args.extensions, excluded_dirs)
    
    # Save results to file
    with open(args.output, "w") as f:
        json.dump(duplicates, f, indent=2)
    
    print(f"Results saved to {args.output}")
    
    # Print results
    for file_hash, file_list in duplicates.items():
        print(f"\nDuplicate files with hash {file_hash}:")
        for filepath in file_list:
            print(f"  - {filepath}")

if __name__ == "__main__":
    main() 