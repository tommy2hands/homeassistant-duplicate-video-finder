# Duplicate Video Finder for Home Assistant

This custom integration for Home Assistant helps you find duplicate video files in your system by comparing their SHA-256 hashes.

## Features

- 🔍 Automatically scans all accessible directories for duplicate video files
- 🎥 Supports common video formats (mp4, avi, mkv, mov, wmv, flv, webm)
- 🎨 User-friendly interface with expandable groups and file details
- ⚡ Efficient file comparison using parallel processing and SHA-256 hashing
- 🔒 Smart directory exclusion to avoid system and sensitive locations
- 📊 Progress tracking and detailed logging
- 🚀 One-click scanning from the UI

## Installation

### Option 1: HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Add this repository as a custom repository in HACS:
   - Go to HACS > Settings > Custom Repositories
   - Add `tommy2hands/homeassistant-duplicate-video-finder` as an Integration
3. Search for "Duplicate Video Finder" in HACS
4. Click "Download"
5. Restart Home Assistant

### Option 2: Manual Installation

1. Copy the `custom_components/duplicate_video_finder` directory to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Usage

### Method 1: Using the Integration

After installation, you should see a "Duplicate Videos" item in your Home Assistant sidebar. If you don't see it, try these steps:

1. Go to Home Assistant Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Duplicate Video Finder"
4. Add the integration
5. Restart Home Assistant

### Method 2: Using the Web Interface Directly

If the sidebar item doesn't appear, you can access the web interface directly:

1. Go to: http://your-home-assistant-url:8123/local/duplicate_video_finder/index.html
2. Enter the directories you want to scan
3. Click "Start Scan"

### Method 3: Using the Standalone Script

If you're having trouble with the integration, you can use the standalone script:

1. Copy the `custom_components/duplicate_video_finder/standalone.py` file to your computer
2. Run it with Python:

```bash
python standalone.py --directories /path/to/videos /another/path --extensions .mp4 .mkv
```

### Service Call

You can also trigger a scan programmatically using the service:

```yaml
service: duplicate_video_finder.find_duplicates
data:
  video_extensions:  # Optional, defaults to common video extensions
    - .mp4
    - .avi
    - .mkv
```

## Troubleshooting

If you're having trouble with the integration:

1. Check the Home Assistant logs for any errors related to "duplicate_video_finder"
2. Try accessing the web interface directly at http://your-home-assistant-url:8123/local/duplicate_video_finder/index.html
3. Try using the standalone script
4. Make sure your Home Assistant version is 2023.8.0 or higher
5. Try clearing your browser cache and restarting Home Assistant

## Performance Optimizations

This integration includes several performance optimizations:

- **Parallel Processing**: Uses a thread pool to hash multiple files simultaneously
- **Smart Directory Scanning**: Efficiently walks through directories while skipping excluded paths
- **Incremental Scanning**: Processes files in batches to avoid memory issues
- **Error Handling**: Gracefully handles permission errors and inaccessible files

## Notes

- The integration uses SHA-256 hashing to identify duplicate files, which is reliable but may take some time for large files
- The scan automatically excludes system directories and sensitive locations for safety
- For very large media libraries, the initial scan may take several minutes
- The integration is designed to be memory-efficient, even with thousands of video files

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 