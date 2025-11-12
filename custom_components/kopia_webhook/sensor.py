# Copyright 2024 SpaceFrags
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Sensor platform for Kopia Webhook Status."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import dt

from . import DOMAIN, KopiaWebhookDataUpdateCoordinator 

_LOGGER = logging.getLogger(__name__)

# --- Helper Function ---

def _get_path_segment(path: str) -> str | None:
    """Extracts the last segment of a path (the source name) and lowercases it."""
    if not path:
        return None
    
    # Remove trailing slash if present
    path = path.rstrip('/')
    # Split by / and take the last part
    segment = path.split('/')[-1]
    
    return segment.lower() if segment else None

# --- Setup ---

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Kopia Webhook sensors from a config entry based on history limit."""
    coordinator: KopiaWebhookDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = []
    # Create an entity for each slot in the rolling history list
    for i in range(coordinator.history_limit):
        entities.append(KopiaSnapshotHistorySensor(coordinator, i))

    async_add_entities(entities)


# --- Sensor Entity ---

class KopiaSnapshotHistorySensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Representation of a Kopia Webhook sensor for a specific history slot."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:backup-restore"
    
    def __init__(self, coordinator: KopiaWebhookDataUpdateCoordinator, slot_index: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.slot_index = slot_index
        
        # Naming: sensor.kopia_backup_snapshot_1, sensor.kopia_backup_snapshot_2, etc.
        self._attr_name = f"Snapshot Slot {self.slot_index + 1}"
        self._attr_unique_id = f"{coordinator.webhook_id}_snapshot_{self.slot_index + 1}"
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info, linking the entity to a device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=f"Kopia Status ({self.coordinator.webhook_id.replace('_', ' ').title()})", 
            manufacturer="Kopia",
            model="Webhook History Listener",
            configuration_url=f"https://your.homeassistant.url/api/webhook/{self.coordinator.webhook_id}",
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to hass and restoring state."""
        await super().async_added_to_hass()
        
        last_state = await self.async_get_last_state()
        if last_state:
            # Restore the last state (which is now the path segment string)
            if last_state.state != STATE_UNKNOWN:
                self._attr_native_value = last_state.state
            
            # Restore the attributes
            if last_state.attributes:
                self._attr_extra_state_attributes = dict(last_state.attributes)
        
        # Ensure that we immediately update from the coordinator if data for this slot is available
        if len(self.coordinator.data) > self.slot_index and self.coordinator.data[self.slot_index]:
            self._handle_coordinator_update()


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        
        # Retrieve data specifically for this sensor's slot index
        data = self.coordinator.data[self.slot_index]
        
        # --- NEW STATE LOGIC ---
        
        # If the slot is empty (initial state or shifted out), set state to None (Unknown)
        if not data:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            self.async_write_ha_state()
            return
            
        # 1. Determine the new state (the lowercase path segment)
        path_segment = _get_path_segment(data.get("path", ""))
        
        # Set the entity state to the path segment (e.g., "nextcloud")
        self._attr_native_value = path_segment
        
        # 2. Extract and move the timestamp to an attribute
        snapshot_time_str = data.get("end_time")

        if snapshot_time_str:
            snapshot_dt = dt.parse_datetime(snapshot_time_str)
            if snapshot_dt:
                # Store the timestamp in a new, easily accessible attribute
                data["snapshot_timestamp"] = snapshot_dt.isoformat() 
            else:
                _LOGGER.warning("Could not parse timestamp string: %s for slot %d", snapshot_time_str, self.slot_index)
                
        # 3. Use the entire payload (now including snapshot_timestamp) as attributes
        self._attr_extra_state_attributes = data
        
        self.async_write_ha_state()
