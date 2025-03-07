# Duplicate Video Finder for Home Assistant

This custom integration for Home Assistant helps you find duplicate video files in your system by comparing their SHA-256 hashes.

## Features

- Automatically scans all accessible directories for duplicate video files
- Supports common video formats (mp4, avi, mkv, mov, wmv, flv, webm)
- User-friendly interface to display duplicate files
- Efficient file comparison using SHA-256 hashing
- Smart directory exclusion to avoid system and sensitive locations

## Installation

1. Copy the `custom_components/duplicate_video_finder` directory to your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.

## Configuration

1. Go to Home Assistant's Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Duplicate Video Finder"
4. Add the integration

## Usage

### Service Call

To scan for duplicate videos, call the `duplicate_video_finder.find_duplicates` service with the following parameters:

```yaml
service: duplicate_video_finder.find_duplicates
data:
  video_extensions:  # Optional, defaults to common video extensions
    - .mp4
    - .avi
    - .mkv
```

The integration will automatically scan all accessible directories on your system, excluding system directories and sensitive locations.

### Frontend Panel

1. Go to Home Assistant's Settings > Dashboard
2. Click "Add Card"
3. Search for "Duplicate Video Finder"
4. Add the card to your dashboard

The panel will display all duplicate video files found during the last scan, grouped by their SHA-256 hash.

## Notes

- The integration uses SHA-256 hashing to identify duplicate files, which is reliable but may take some time for large files
- The scan automatically excludes system directories and sensitive locations for safety
- The frontend panel will update automatically when new duplicates are found
- The scan starts from common root directories (/home, /media, /mnt, /storage) and recursively searches for video files 