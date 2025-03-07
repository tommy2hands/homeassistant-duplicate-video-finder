"""The Duplicate Video Finder integration."""
from __future__ import annotations

import logging
import os
import shutil
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.loader import bind_hass

from .const import DOMAIN
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({})
    },
    extra=vol.ALLOW_EXTRA,
)

PANEL_URL = "/duplicate-video-finder"
PANEL_TITLE = "Duplicate Videos"
PANEL_ICON = "mdi:file-video"
PANEL_NAME = "duplicate-video-finder"

@callback
@bind_hass
def add_duplicate_video_finder_panel(hass: HomeAssistant) -> None:
    """Add the Duplicate Video Finder panel to the sidebar."""
    # Try all methods to register the panel
    try:
        # Method 1: Register as a custom panel
        hass.components.frontend.async_register_built_in_panel(
            "custom",
            PANEL_TITLE,
            PANEL_ICON,
            PANEL_NAME,
            require_admin=False,
        )
        _LOGGER.info("Panel registered as custom panel")
    except Exception as err:
        _LOGGER.error("Error registering custom panel: %s", err)

    try:
        # Method 2: Register as an iframe panel
        hass.components.frontend.async_register_built_in_panel(
            "iframe",
            PANEL_TITLE,
            PANEL_ICON,
            PANEL_NAME,
            {"url": "/local/duplicate_video_finder/duplicate-video-finder-panel.html"},
            require_admin=False,
        )
        _LOGGER.info("Panel registered as iframe panel")
    except Exception as err:
        _LOGGER.error("Error registering iframe panel: %s", err)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Duplicate Video Finder integration."""
    # Initialize component data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["duplicates"] = {}
    
    # Create local directory for frontend files
    local_dir = hass.config.path("www", "duplicate_video_finder")
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    
    # Copy frontend files to www directory
    try:
        # Copy HTML file
        html_source = os.path.join(
            os.path.dirname(__file__), "frontend", "duplicate-video-finder-panel.html"
        )
        html_dest = os.path.join(local_dir, "duplicate-video-finder-panel.html")
        
        # Copy JS file
        js_source = os.path.join(
            os.path.dirname(__file__), "frontend", "duplicate-video-finder-panel.js"
        )
        js_dest = os.path.join(local_dir, "duplicate-video-finder-panel.js")
        
        # Copy files
        await hass.async_add_executor_job(shutil.copy2, html_source, html_dest)
        await hass.async_add_executor_job(shutil.copy2, js_source, js_dest)
        
        _LOGGER.info("Frontend files copied to %s", local_dir)
    except Exception as err:
        _LOGGER.error("Error copying frontend files: %s", err)
    
    # Register the panel
    add_duplicate_video_finder_panel(hass)
    
    # Set up services
    await async_setup_services(hass)
    
    # Create a config entry if one doesn't exist
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data={}
            )
        )
    
    return True

class DuplicateVideoFinderView(HomeAssistantView):
    """View to serve the duplicate video finder panel."""

    requires_auth = True
    name = "duplicate_video_finder:panel"
    url = PANEL_URL

    def __init__(self, hass):
        """Initialize the view."""
        self.hass = hass

    async def get(self, request):
        """Handle GET request."""
        html_file = self.hass.config.path("www", "duplicate_video_finder", "duplicate-video-finder-panel.html")
        
        try:
            with open(html_file, "r") as file:
                html = file.read()
                return self.json({"html_content": html})
        except Exception as err:
            _LOGGER.error("Error serving panel HTML: %s", err)
            return self.json({"error": str(err)})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Duplicate Video Finder from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config_entry"] = entry
    
    # Register the panel
    add_duplicate_video_finder_panel(hass)
    
    # Set up services
    await async_setup_services(hass)
    
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