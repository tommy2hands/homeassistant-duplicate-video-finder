"""Sensor platform for Duplicate Video Finder integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.const import STATE_IDLE
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, SCAN_STATE_UPDATED, SCAN_STATE_ENTITY_ID

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Duplicate Video Finder sensor."""
    _LOGGER.info("Setting up Duplicate Video Finder sensor")
    
    # Only add sensor if it doesn't already exist
    if hass.states.get(SCAN_STATE_ENTITY_ID) is None:
        _LOGGER.info("Creating new sensor entity")
        sensor = DuplicateVideoFinderSensor(hass)
        async_add_entities([sensor], True)
    else:
        _LOGGER.info("Sensor entity already exists")


class DuplicateVideoFinderSensor(SensorEntity):
    """Sensor for tracking duplicate video scan state."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self.entity_id = SCAN_STATE_ENTITY_ID
        self._name = "Duplicate Video Finder Scan State"
        self._state = STATE_IDLE
        self._attrs = {
            "progress": 0,
            "current_file": "",
            "total_files": 0,
            "processed_files": 0,
            "found_duplicates": {},
        }
        _LOGGER.info("Initializing %s", self.entity_id)

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        # Listen for state updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SCAN_STATE_UPDATED, self._update_callback
            )
        )
        
        # Read current scan state from hass.data
        await self._update_from_data()
        
        # Immediately write state to make sure it's not unavailable
        self.async_write_ha_state()
        _LOGGER.info("Sensor %s added to hass with state %s", self.entity_id, self._state)

    @callback
    def _update_callback(self) -> None:
        """Update the entity when scan state changes."""
        _LOGGER.debug("Received scan state update")
        self.hass.async_create_task(self._update_from_data())

    async def _update_from_data(self) -> None:
        """Update state and attributes from hass.data."""
        if DOMAIN not in self.hass.data:
            _LOGGER.warning("Domain data not found, using defaults")
            self._state = STATE_IDLE
            return
            
        scan_state = self.hass.data[DOMAIN].get("scan_state", {})
        _LOGGER.debug("Updating from scan state: %s", scan_state)
        
        # Determine state
        if scan_state.get("is_scanning", False):
            if scan_state.get("is_paused", False):
                self._state = "paused"
            else:
                self._state = "scanning"
        else:
            self._state = STATE_IDLE
            
        # Calculate progress
        processed = scan_state.get("processed_files", 0)
        total = max(scan_state.get("total_files", 1), 1)
        progress = round((processed / total) * 100, 1) if total > 0 else 0
            
        # Update attributes
        self._attrs = {
            "progress": progress,
            "current_file": scan_state.get("current_file", ""),
            "total_files": total,
            "processed_files": processed,
            "found_duplicates": scan_state.get("found_duplicates", {}),
            "friendly_name": self._name,
        }
        
        # Write state to Home Assistant
        self.async_write_ha_state()
        _LOGGER.debug("Updated sensor %s to state %s with progress %s", 
                     self.entity_id, self._state, progress)
    
    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name
        
    @property
    def state(self) -> str:
        """Return the state of the entity."""
        return self._state
        
    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return self._attrs
        
    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:file-video" 