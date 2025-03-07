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

After installation, you'll see a new "Duplicate Videos" item in your Home Assistant sidebar. Click on it to access the Duplicate Video Finder interface.

### Finding Duplicates

1. Open the Duplicate Video Finder panel from the sidebar
2. Click the "Start Scan" button
3. Wait for the scan to complete (this may take some time depending on the number of files)
4. Review the results, organized by duplicate groups

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

## Troubleshooting

If you encounter any issues:

1. Check the Home Assistant logs for detailed error messages
2. Ensure Home Assistant has read access to your media directories
3. For very large libraries, consider increasing the Home Assistant timeout settings
4. If the scan seems stuck, check the logs for progress updates

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 