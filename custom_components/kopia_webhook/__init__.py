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
DATA_KEY = f"{DOMAIN}.coordinator"

# --- Custom Text Parsing Function (for Plain Text payload) ---
def _parse_kopia_plain_text(text: str) -> dict[str, Any]:
    """Parses the plain text Kopia webhook payload into a dictionary."""
    data = {}
    
    # Regex to find (Key: ) and capture (Value) until the next Key: or end of string.
    pattern = re.compile(r'([A-Z][a-z]+(?: [a-z]+)*):\s*(.*?)(?=\s[A-Z][a-z]+(?: [a-z]+)*:|\Z)', re.DOTALL)
    
    matches = pattern.findall(text)
    
    for key, value in matches:
        normalized_key = key.strip().lower().replace(' ', '_')
        data[normalized_key] = value.strip()

    # Map the 'start' field to 'end_time' for sensor compatibility
    if 'start' in data:
        data['end_time'] = data['start'] 
        
    return data

# --- Coordinator ---

class KopiaWebhookDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator to manage webhook data updates using a rolling history list."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None, 
        )
        self.entry = entry
        self.webhook_id = entry.data.get("webhook_id", entry.entry_id) 
        self.history_limit = entry.data.get("history_limit", 10) # Get the limit
        
        # CHANGE: Data is now a LIST of snapshot dictionaries (rolling history)
        # Initialize with empty dictionaries up to the limit
        self.data: list[dict[str, Any]] = [{} for _ in range(self.history_limit)]

    def update_data(self, payload: dict[str, Any]) -> None:
        """
        Update the coordinator's data by implementing rolling history.
        New payload goes to index 0, old data shifts down, oldest is discarded.
        """
        # 1. Shift existing data down (data[N] becomes data[N+1])
        # We start from the end (limit - 1) and move the previous slot's content (i-1)
        for i in range(self.history_limit - 1, 0, -1):
            self.data[i] = self.data[i-1]
            
        # 2. Insert the new payload at the head of the list (index 0)
        self.data[0] = payload
        
        # 3. Notify sensors
        self.async_set_updated_data(self.data)


# --- Setup and Unload ---

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kopia Webhook Status from a config entry."""
    
    # Store the coordinator instance
    coordinator = KopiaWebhookDataUpdateCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    webhook_id = entry.data["webhook_id"] # Use the user-defined ID for the URL

    @callback
    async def handle_webhook(hass: HomeAssistant, webhook_id: str, request: web.Request) -> web.Response | None:
        """Handle incoming webhook from Kopia."""
        _LOGGER.debug("Received webhook for ID: %s", webhook_id)

        coordinator_instance: KopiaWebhookDataUpdateCoordinator = hass.data[DOMAIN].get(entry.entry_id)

        if not coordinator_instance:
            _LOGGER.warning("Coordinator not found for entry ID: %s (Webhook ID: %s)", entry.entry_id, webhook_id)
            return web.Response(status=404)

        try:
            # Read the body as plain text, then parse it manually
            request_body_text = await request.text()
            if not request_body_text:
                _LOGGER.error("Received empty webhook body from ID '%s'. Check Kopia configuration.", webhook_id)
                return web.Response(status=400, text="Empty payload received.")

            # Parse the plain text body into a usable dictionary
            payload = _parse_kopia_plain_text(request_body_text)

        except Exception as err:
            _LOGGER.error(
                "Error processing webhook payload from ID '%s': %s. "
                "Received body (first 200 chars): '%s'",
                webhook_id, err, request_body_text[:200]
            )
            return web.Response(status=400, text=f"Error processing payload: {err}")
        
        if not payload:
            _LOGGER.warning(
                "Webhook payload from ID '%s' was received but no data could be parsed.",
                webhook_id
            )
            return web.Response(status=400, text="Could not parse data from payload.")

        # Update the coordinator with the new data
        coordinator_instance.update_data(payload)
        
        # Return success response
        return web.Response(status=200, text="OK")


    # Register the webhook handler. 
    try:
        async_register(
            hass,
            DOMAIN,
            "Kopia",
            webhook_id,
            handle_webhook,
        )
        _LOGGER.info("Kopia Webhook registered successfully with ID: %s", webhook_id)
        _LOGGER.info("Webhook URL: %s", async_generate_url(hass, webhook_id))

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
