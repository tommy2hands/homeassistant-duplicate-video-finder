"""The Duplicate Video Finder integration."""
from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.frontend import async_register_built_in_panel

from .const import DOMAIN
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({})
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Duplicate Video Finder integration."""
    # Initialize component data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["duplicates"] = {}
    
    # Register the panel
    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Duplicate Videos",
        sidebar_icon="mdi:file-video",
        frontend_url_path="duplicate-video-finder",
        require_admin=False,
        config={
            "_panel_custom": {
                "name": "duplicate-video-finder-panel",
                "module_url": "/local/duplicate_video_finder/duplicate-video-finder-panel.js",
                "embed_iframe": False,
            }
        },
    )
    
    # Create local directory for frontend files
    local_dir = hass.config.path("www", "duplicate_video_finder")
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    
    # Copy frontend file to www directory
    frontend_source = os.path.join(
        os.path.dirname(__file__), "frontend", "duplicate-video-finder-panel.js"
    )
    frontend_dest = os.path.join(local_dir, "duplicate-video-finder-panel.js")
    
    try:
        with open(frontend_source, "r") as source_file:
            content = source_file.read()
            
        with open(frontend_dest, "w") as dest_file:
            dest_file.write(content)
            
        _LOGGER.info("Frontend file copied to %s", frontend_dest)
    except Exception as err:
        _LOGGER.error("Error copying frontend file: %s", err)
    
    # Set up services
    await async_setup_services(hass)
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Duplicate Video Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config_entry"] = entry
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Remove services
    for service in hass.services.async_services().get(DOMAIN, {}):
        hass.services.async_remove(DOMAIN, service)
    
    # Clean up data
    if DOMAIN in hass.data:
        hass.data.pop(DOMAIN)
    
    return True 