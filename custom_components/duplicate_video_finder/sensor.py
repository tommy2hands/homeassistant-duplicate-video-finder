"""Sensor platform for Duplicate Video Finder integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.const import STATE_IDLE
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SCAN_STATE_UPDATED

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Duplicate Video Finder sensor."""
    _LOGGER.info("Setting up Duplicate Video Finder sensor entity")
    
    # Initialize the scan state in hass.data if not already there
    hass.data.setdefault(DOMAIN, {})
    if "scan_state" not in hass.data[DOMAIN]:
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
    
    # Create and add the sensor entity
    scan_state_sensor = DuplicateVideoFinderSensor(hass)
    async_add_entities([scan_state_sensor], True)
    
    # Store the entity in hass.data for services to use
    hass.data[DOMAIN].setdefault("entities", [])
    hass.data[DOMAIN]["entities"].append(scan_state_sensor.entity_id)
    
    _LOGGER.info("Duplicate Video Finder sensor setup complete")


class DuplicateVideoFinderSensor(RestoreEntity, SensorEntity):
    """Sensor for tracking duplicate video scan state."""

    _attr_has_entity_name = True
    _attr_name = "Scan State"
    _attr_icon = "mdi:file-video"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._attr_unique_id = f"{DOMAIN}_scan_state"
        self.entity_id = f"sensor.{DOMAIN}_scan_state"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "duplicate_video_finder")},
            "name": "Duplicate Video Finder",
            "manufacturer": "Home Assistant Community",
            "model": "Integration",
            "sw_version": "1.1.8",
        }
        
        # Set initial state - important to not be "unavailable"
        self._attr_native_value = STATE_IDLE
        self._attr_extra_state_attributes = {
            "progress": 0,
            "current_file": "",
            "total_files": 0,
            "processed_files": 0,
            "found_duplicates": {},
        }
        
        # Log initialization
        _LOGGER.info(f"Duplicate Video Finder sensor initialized: {self.entity_id}")

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        last_state = await self.async_get_last_state()
        if last_state:
            self._attr_native_value = last_state.state
            
            # Restore attributes if available
            if last_state.attributes:
                for key, value in last_state.attributes.items():
                    if key in self._attr_extra_state_attributes:
                        self._attr_extra_state_attributes[key] = value
        
        # Listen for scan state updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SCAN_STATE_UPDATED, self._update_callback
            )
        )
        
        # Initial update from current scan state and write to HA state
        self._update_attributes()
        self.async_write_ha_state()
        
        _LOGGER.info(f"Duplicate Video Finder sensor added to hass with state: {self._attr_native_value}")

    @callback
    def _update_callback(self) -> None:
        """Update the entity when scan state changes."""
        _LOGGER.debug("Scan state update received")
        self._update_attributes()
        self.async_write_ha_state()

    @callback
    def _update_attributes(self) -> None:
        """Update the sensor state and attributes from scan_state."""
        if DOMAIN not in self.hass.data or "scan_state" not in self.hass.data[DOMAIN]:
            # Default to idle if no scan state is available
            self._attr_native_value = STATE_IDLE
            return
        
        # Get the current scan state
        scan_state = self.hass.data[DOMAIN].get("scan_state", {})
        _LOGGER.debug(f"Updating sensor with scan state: {scan_state}")
        
        # Determine the state value
        if scan_state.get("is_scanning", False):
            if scan_state.get("is_paused", False):
                self._attr_native_value = "paused"
            else:
                self._attr_native_value = "scanning"
        else:
            self._attr_native_value = STATE_IDLE
        
        # Calculate progress
        processed = scan_state.get("processed_files", 0)
        total = max(scan_state.get("total_files", 1), 1)  # Avoid division by zero
        progress = round((processed / total) * 100, 1) if total > 0 else 0
        
        # Set attributes
        self._attr_extra_state_attributes = {
            "progress": progress,
            "current_file": scan_state.get("current_file", ""),
            "total_files": total,
            "processed_files": processed,
            "found_duplicates": scan_state.get("found_duplicates", {}),
        }
        
        _LOGGER.debug(f"Sensor updated: state={self._attr_native_value}, progress={progress}") 