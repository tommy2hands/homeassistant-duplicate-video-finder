"""Sensor platform for Duplicate Video Finder integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, SCAN_STATE_UPDATED

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Duplicate Video Finder sensor."""
    scan_state_sensor = DuplicateVideoFinderSensor(hass)
    async_add_entities([scan_state_sensor], True)


class DuplicateVideoFinderSensor(SensorEntity):
    """Sensor for tracking duplicate video scan state."""

    _attr_has_entity_name = True
    _attr_name = "Scan State"
    _attr_icon = "mdi:file-video"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._attr_unique_id = f"{DOMAIN}_scan_state"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "duplicate_video_finder")},
            "name": "Duplicate Video Finder",
            "manufacturer": "Home Assistant Community",
            "model": "Integration",
            "sw_version": "1.1.7",
        }
        self._update_attributes()

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SCAN_STATE_UPDATED, self._update_callback
            )
        )

    @callback
    def _update_callback(self) -> None:
        """Update the entity when scan state changes."""
        self._update_attributes()
        self.async_write_ha_state()

    @callback
    def _update_attributes(self) -> None:
        """Update the sensor state and attributes from scan_state."""
        if DOMAIN not in self.hass.data:
            self._attr_state = "idle"
            self._attr_extra_state_attributes = {}
            return

        scan_state = self.hass.data[DOMAIN].get("scan_state", {})
        
        # Determine the state value
        if scan_state.get("is_scanning", False):
            if scan_state.get("is_paused", False):
                self._attr_state = "paused"
            else:
                self._attr_state = "scanning"
        else:
            self._attr_state = "idle"
        
        # Set attributes
        self._attr_extra_state_attributes = {
            "progress": round(scan_state.get("processed_files", 0) / 
                        max(scan_state.get("total_files", 1), 1) * 100, 1),
            "current_file": scan_state.get("current_file", ""),
            "total_files": scan_state.get("total_files", 0),
            "processed_files": scan_state.get("processed_files", 0),
            "found_duplicates": scan_state.get("found_duplicates", {}),
        }
        
        # Ensure the sensor is properly registered in Home Assistant
        if (
            DOMAIN in self.hass.data
            and "entities" in self.hass.data[DOMAIN]
            and self.entity_id not in self.hass.data[DOMAIN]["entities"]
        ):
            self.hass.data[DOMAIN]["entities"].append(self.entity_id) 