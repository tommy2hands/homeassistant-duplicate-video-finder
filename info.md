{% if installed %}
## Thank you for installing!

Remember to restart Home Assistant after installation.

{% endif %}

# Duplicate Video Finder

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![Validate](https://github.com/{{ repository }}/actions/workflows/validate.yml/badge.svg)](https://github.com/{{ repository }}/actions/workflows/validate.yml)

A Home Assistant integration that automatically finds duplicate video files across your system by comparing their SHA-256 hashes.

{% if installed %}
## Current version: {{ version }}

{% endif %}

## Features

- 🔍 Automatically scans all accessible directories for duplicate video files
- 🎥 Supports common video formats (mp4, avi, mkv, mov, wmv, flv, webm)
- 🎨 User-friendly interface to display duplicate files
- ⚡ Efficient file comparison using SHA-256 hashing
- 🔒 Smart directory exclusion to avoid system and sensitive locations
- 📊 Progress tracking and detailed logging

## Installation

### Option 1: HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Add this repository as a custom repository in HACS
3. Search for "Duplicate Video Finder" in HACS
4. Click "Download"
5. Restart Home Assistant

### Option 2: Manual Installation

1. Copy the `custom_components/duplicate_video_finder` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

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

## Support

If you're having issues, please [report them](https://github.com/{{ repository }}/issues)

## Contributing

Feel free to contribute to this project by:

1. Forking the repository
2. Creating a feature branch
3. Committing your changes
4. Pushing to the branch
5. Creating a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 