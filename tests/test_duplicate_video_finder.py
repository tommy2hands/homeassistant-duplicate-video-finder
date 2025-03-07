"""Test the Duplicate Video Finder integration."""
import os
import pytest
from unittest.mock import patch, MagicMock

from custom_components.duplicate_video_finder.services import (
    calculate_file_hash,
    is_excluded_directory,
    find_duplicate_videos,
)

@pytest.fixture
def mock_hass():
    """Create a mock hass object."""
    hass = MagicMock()
    return hass

def test_calculate_file_hash(tmp_path):
    """Test file hash calculation."""
    # Create a test file with known content
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")
    
    # Calculate hash
    hash_value = calculate_file_hash(str(test_file))
    
    # Verify hash is not empty and is a valid hex string
    assert hash_value
    assert len(hash_value) == 64
    assert all(c in '0123456789abcdef' for c in hash_value)

def test_is_excluded_directory():
    """Test directory exclusion logic."""
    # Test excluded directories
    assert is_excluded_directory("/proc/something")
    assert is_excluded_directory("/sys/class")
    assert is_excluded_directory("/dev/sda1")
    
    # Test non-excluded directories
    assert not is_excluded_directory("/home/user/videos")
    assert not is_excluded_directory("/media/storage")
    assert not is_excluded_directory("/mnt/external")

@pytest.mark.asyncio
async def test_find_duplicate_videos(mock_hass, tmp_path):
    """Test duplicate video finding functionality."""
    # Create test directories and files
    test_dir = tmp_path / "test_videos"
    test_dir.mkdir()
    
    # Create two identical files
    file1 = test_dir / "video1.mp4"
    file2 = test_dir / "video2.mp4"
    file1.write_text("test content")
    file2.write_text("test content")
    
    # Create a different file
    file3 = test_dir / "video3.mp4"
    file3.write_text("different content")
    
    # Mock the get_accessible_directories function
    with patch('custom_components.duplicate_video_finder.services.get_accessible_directories') as mock_get_dirs:
        mock_get_dirs.return_value = [str(test_dir)]
        
        # Find duplicates
        duplicates = await find_duplicate_videos(mock_hass)
        
        # Verify results
        assert len(duplicates) == 1  # One group of duplicates
        assert len(duplicates[list(duplicates.keys())[0]]) == 2  # Two files in the group
        assert str(file1) in duplicates[list(duplicates.keys())[0]]
        assert str(file2) in duplicates[list(duplicates.keys())[0]] 