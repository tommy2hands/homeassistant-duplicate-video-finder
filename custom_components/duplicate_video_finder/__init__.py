"""The Duplicate Video Finder integration."""
from __future__ import annotations

import logging
import os
import shutil
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.const import Platform
from homeassistant.helpers.entity_component import EntityComponent

from .const import DOMAIN, SCAN_STATE_ENTITY_ID
from .services import async_setup_services
from .sensor import DuplicateVideoFinderSensor

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({})
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.SENSOR]

PANEL_URL = "/duplicate-video-finder"
PANEL_TITLE = "Duplicate Videos"
PANEL_ICON = "mdi:file-video"
PANEL_NAME = "duplicate-video-finder"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Duplicate Video Finder integration."""
    # Initialize component data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["duplicates"] = {}
    hass.data[DOMAIN]["entities"] = []

    # Initialize default scan state
    hass.data[DOMAIN]["scan_state"] = {
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
    }
    
    # Create local directory for frontend files
    local_dir = hass.config.path("www", "duplicate_video_finder")
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    
    # Copy frontend files to www directory
    try:
        # Copy JS file
        js_source = os.path.join(
            os.path.dirname(__file__), "frontend", "duplicate-video-finder-panel.js"
        )
        js_dest = os.path.join(local_dir, "duplicate-video-finder-panel.js")
        
        # Copy files
        await hass.async_add_executor_job(shutil.copy2, js_source, js_dest)
        
        _LOGGER.info("Frontend files copied to %s", local_dir)
    except Exception as err:
        _LOGGER.error("Error copying frontend files: %s", err)
    
    # Register the panel
    try:
        # Register the panel directly
        hass.components.frontend.async_register_built_in_panel(
            "custom",
            PANEL_TITLE,
            PANEL_ICON,
            PANEL_NAME,
            {"_panel_custom": {
                "name": "duplicate-video-finder-panel",
                "module_url": "/local/duplicate_video_finder/duplicate-video-finder-panel.js",
                "embed_iframe": False,
            }},
            require_admin=False,
        )
        _LOGGER.info("Panel registered successfully")
    except Exception as err:
        _LOGGER.error("Error registering panel: %s", err)
    
    # Set up services
    await async_setup_services(hass)
    
    # Create a config entry if one doesn't exist
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data={}
            )
        )
    
    # Manually register the sensor entity to ensure it's available
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    sensor = DuplicateVideoFinderSensor(hass)
    await component.async_add_entities([sensor])
    _LOGGER.info("Created sensor entity: %s", sensor.entity_id)
    
    # Force state update for the scan state entity
    hass.states.async_set(
        SCAN_STATE_ENTITY_ID,
        "idle",
        {
            "progress": 0,
            "current_file": "",
            "total_files": 0,
            "processed_files": 0,
            "friendly_name": "Scan State",
        }
    )
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Duplicate Video Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config_entry"] = entry
    
    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Remove services
    for service in hass.services.async_services().get(DOMAIN, {}):
        hass.services.async_remove(DOMAIN, service)
    
    # Clean up data
    if DOMAIN in hass.data:
        hass.data.pop(DOMAIN)
    
    return unload_ok 