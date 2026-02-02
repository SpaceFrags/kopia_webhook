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
"""The Kopia Webhook Status integration."""
from __future__ import annotations

import logging
import json
import re 
from typing import Any

from aiohttp import web
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.webhook import (
    async_register, 
    async_unregister, 
    async_generate_url
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "kopia_webhook"
PLATFORMS = ["sensor"]

# --- Custom Text Parsing Function (for Plain Text payload) ---
def _parse_kopia_plain_text(text: str) -> dict[str, Any]:
    """Parses the plain text Kopia webhook payload into a dictionary."""
    data = {}
    
    # Regex to find (Key: ) and capture (Value) until the next Key: or end of string.
    pattern = re.compile(r"([a-zA-Z\s]+):\s*(.*)")
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            # Normalize keys to snake_case (e.g., "Source Path" -> "source_path")
            key = match.group(1).strip().lower().replace(" ", "_")
            value = match.group(2).strip()
            data[key] = value
    return data

class KopiaWebhookDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage Kopia webhook data with history slots."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, webhook_id: str, history_limit: int) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry = entry  # FIX: Store entry so sensor.py can access entry_id
        self.webhook_id = webhook_id
        self.history_limit = history_limit
        # Initialize the list with None for all slots
        self.data = [None] * self.history_limit

    def update_data(self, new_snapshot: dict[str, Any]) -> None:
        """Update the internal data list (shifting old ones down)."""
        # Add new snapshot to the front
        self.data.insert(0, new_snapshot)
        # Keep only the last N snapshots based on history_limit
        self.data = self.data[:self.history_limit]
        self.async_set_updated_data(self.data)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kopia Webhook Status from a config entry."""
    webhook_id = entry.data["webhook_id"]
    history_limit = entry.data.get("history_limit", 10)

    # Initialize coordinator with entry reference to prevent sensor.py crash
    coordinator = KopiaWebhookDataUpdateCoordinator(hass, entry, webhook_id, history_limit)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def handle_webhook(hass, webhook_id, request):
        """Handle incoming webhook (supports JSON and Plain Text)."""
        _LOGGER.debug("Kopia Webhook received for ID: %s", webhook_id)
        
        # Access the coordinator instance
        coordinator_instance = hass.data[DOMAIN][entry.entry_id]
        
        payload = {}
        try:
            # Check content type to decide how to parse
            if request.content_type == "application/json":
                payload = await request.json()
            else:
                # Fallback to plain text parsing
                body = await request.text()
                payload = _parse_kopia_plain_text(body)
        except Exception as err:
            _LOGGER.error("Error decoding Kopia webhook payload: %s", err)
            return web.Response(status=400, text="Invalid payload format")

        if not payload:
            _LOGGER.warning("Kopia Webhook received empty payload")
            return web.Response(status=400, text="Empty payload")

        # Update the coordinator with the new data
        coordinator_instance.update_data(payload)
        
        # Return success response
        return web.Response(status=200, text="OK")

    # Register the webhook handler
    try:
        async_register(
            hass,
            DOMAIN,
            "Kopia",
            webhook_id,
            handle_webhook,
        )
        
        # This generates the URL based on your HA configuration (Internal/External URL)
        webhook_url = async_generate_url(hass, webhook_id)
        _LOGGER.info("Kopia Webhook registered successfully with ID: %s", webhook_id)
        _LOGGER.info("Webhook URL: %s", webhook_url)

    except ValueError:
        _LOGGER.debug("Kopia Webhook handler already registered for ID: %s", webhook_id)
        pass 

    # Forward the setup to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Unregister the webhook
    try:
        async_unregister(hass, entry.data["webhook_id"]) 
        _LOGGER.info("Kopia Webhook unregistered successfully for ID: %s", entry.data["webhook_id"])
    except Exception as err:
        _LOGGER.warning("Could not unregister Kopia Webhook: %s", err)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
