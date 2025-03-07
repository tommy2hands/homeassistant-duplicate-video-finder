"""Diagnostics for Duplicate Video Finder."""
import os
import logging
import json
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    _LOGGER.info("Generating diagnostics for Duplicate Video Finder")
    
    # Check if the integration is properly loaded
    integration_loaded = "duplicate_video_finder" in hass.data
    
    # Check if the panel is registered
    panels = list(hass.data.get("frontend_panels", {}).keys())
    panel_registered = "duplicate-video-finder" in panels
    
    # Check if the service is registered
    services = hass.services.async_services()
    service_registered = "duplicate_video_finder" in services and "find_duplicates" in services.get("duplicate_video_finder", {})
    
    # Check if the frontend files exist
    www_dir = hass.config.path("www", "duplicate_video_finder")
    html_file = os.path.join(www_dir, "duplicate-video-finder-panel.html")
    js_file = os.path.join(www_dir, "duplicate-video-finder-panel.js")
    
    frontend_files_exist = os.path.exists(html_file) and os.path.exists(js_file)
    
    # Check component files
    component_dir = os.path.dirname(__file__)
    manifest_file = os.path.join(component_dir, "manifest.json")
    init_file = os.path.join(component_dir, "__init__.py")
    services_file = os.path.join(component_dir, "services.py")
    
    component_files_exist = (
        os.path.exists(manifest_file) 
        and os.path.exists(init_file) 
        and os.path.exists(services_file)
    )
    
    # Get manifest content
    manifest_content = {}
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, "r") as f:
                manifest_content = json.load(f)
        except Exception as err:
            _LOGGER.error("Error reading manifest.json: %s", err)
    
    # Create diagnostics report
    diagnostics = {
        "integration_loaded": integration_loaded,
        "panel_registered": panel_registered,
        "service_registered": service_registered,
        "frontend_files_exist": frontend_files_exist,
        "component_files_exist": component_files_exist,
        "panels": panels,
        "manifest": manifest_content,
        "www_dir_exists": os.path.exists(www_dir),
        "html_file_exists": os.path.exists(html_file),
        "js_file_exists": os.path.exists(js_file),
    }
    
    _LOGGER.info("Diagnostics generated: %s", diagnostics)
    
    return diagnostics 