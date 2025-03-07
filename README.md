# Duplicate Video Finder for Home Assistant

This custom integration for Home Assistant helps you find duplicate video files in your system by comparing their SHA-256 hashes.

## Features

- 🔍 Automatically scans all directories under `/home/*` for duplicate video files
- 🎥 Supports common video formats (mp4, avi, mkv, mov, wmv, flv, webm)
- 🎨 User-friendly interface with expandable groups and file details
- ⚡ Efficient file comparison using parallel processing and SHA-256 hashing
- 🔒 Smart directory exclusion to avoid system and sensitive locations
- 📊 Real-time progress tracking with current file display
- 🚀 One-click scanning from the UI
- ⏸️ Pause, resume, and cancel scanning operations
- 🖥️ CPU usage management to prevent system slowdowns
- 💾 Memory optimization with batch processing

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

### Using the Interface

1. Click on "Duplicate Videos" in the sidebar
2. (Optional) Adjust advanced options:
   - **Max CPU Usage**: Limit CPU usage during scanning (default: 70%)
   - **Batch Size**: Number of files to process in a batch (default: 100)
   - **Video Extensions**: Customize which file types to scan
3. Click "Start Scan" to begin
4. During scanning:
   - View real-time progress with percentage and current file
   - Pause/Resume the scan at any time
   - Cancel the scan if needed
5. Review results organized by duplicate groups

### Service Calls

You can also trigger operations programmatically using these services:

#### Find Duplicates
```yaml
service: duplicate_video_finder.find_duplicates
data:
  video_extensions:  # Optional, defaults to common video extensions
    - .mp4
    - .avi
    - .mkv
  max_cpu_percent: 70  # Optional, default is 70%
  batch_size: 100  # Optional, default is 100
```

#### Pause Scan
```yaml
service: duplicate_video_finder.pause_scan
```

#### Resume Scan
```yaml
service: duplicate_video_finder.resume_scan
```

#### Cancel Scan
```yaml
service: duplicate_video_finder.cancel_scan
```

## Performance Optimizations

This integration includes several performance optimizations:

- **CPU Management**: Limits CPU usage to prevent system slowdowns
- **Memory Optimization**: Processes files in batches to manage memory usage
- **Parallel Processing**: Uses a thread pool to hash multiple files simultaneously
- **Smart Directory Scanning**: Efficiently walks through directories while skipping excluded paths
- **Pause/Resume**: Allows pausing resource-intensive scans during high system load
- **Progress Tracking**: Shows real-time progress and current file being processed

## Notes

- The integration uses SHA-256 hashing to identify duplicate files, which is reliable but may take some time for large files
- The scan automatically excludes system directories and sensitive locations for safety
- For very large media libraries, consider using a lower CPU percentage and smaller batch size
- The integration is designed to be memory-efficient, even with thousands of video files

## Troubleshooting

If you're having trouble with the integration:

1. Check the Home Assistant logs for any errors related to "duplicate_video_finder"
2. Try accessing the web interface directly at http://your-home-assistant-url:8123/local/duplicate_video_finder/index.html
3. Try using the standalone script
4. Make sure your Home Assistant version is 2023.8.0 or higher
5. Try clearing your browser cache and restarting Home Assistant

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 