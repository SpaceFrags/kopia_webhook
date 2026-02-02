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

def _parse_kopia_plain_text(text: str) -> dict[str, Any]:
    """Parses plain text Kopia payload to match the original attribute format."""
    data = {}
    lines = text.splitlines()
    
    # Mapping for original attribute keys
    key_map = {
        "Path": "path",
        "Status": "status",
        "Start": "start",
        "Duration": "duration",
        "Size": "size",
        "Files": "files",
        "Directories": "directories"
    }

    current_key = None
    current_value = []

    for line in lines:
        # Match "Key: Value" pattern
        match = re.match(r"^([a-zA-Z\s]+):\s*(.*)$", line)
        if match:
            # Save previous key's data
            if current_key:
                data[current_key] = "\n".join(current_value).strip()
            
            raw_key = match.group(1).strip()
            current_key = key_map.get(raw_key, raw_key.lower().replace(" ", "_"))
            current_value = [match.group(2)]
        else:
            # Handle multi-line data (like the footer or directory details)
            if current_key:
                current_value.append(line)

    # Save final key
    if current_key:
        data[current_key] = "\n".join(current_value).strip()

    # --- RESTORE ORIGINAL ATTRIBUTE NAMES/LOGIC ---
    
    # 1. Ensure end_time exists (matches old sensor logic)
    if "start" in data and "end_time" not in data:
        data["end_time"] = data["start"]

    # 2. Cleanup 'directories' to include the full original footer
    if "directories" in data and "Generated at" not in data["directories"]:
        footer_match = re.search(r"(Generated at .* by Kopia .*https://kopia.io/)", text, re.DOTALL)
        if footer_match:
            data["directories"] = data["directories"] + "\n\n" + footer_match.group(1)

    return data

class KopiaWebhookDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage Kopia webhook data with history slots."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, webhook_id: str, history_limit: int) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.entry = entry  # Sensor.py needs this for device_info
        self.webhook_id = webhook_id
        self.history_limit = history_limit
        self.data = [None] * self.history_limit

    def update_data(self, new_snapshot: dict[str, Any]) -> None:
        """Update the internal data list (shifting old ones down)."""
        self.data.insert(0, new_snapshot)
        self.data = self.data[:self.history_limit]
        self.async_set_updated_data(self.data)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kopia Webhook Status from a config entry."""
    webhook_id = entry.data["webhook_id"]
    history_limit = entry.data.get("history_limit", 10)

    coordinator = KopiaWebhookDataUpdateCoordinator(hass, entry, webhook_id, history_limit)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def handle_webhook(hass, webhook_id, request):
        """Handle incoming webhook (supports JSON and Plain Text)."""
        _LOGGER.debug("Kopia Webhook received for ID: %s", webhook_id)
        coordinator_instance = hass.data[DOMAIN][entry.entry_id]
        
        payload = {}
        try:
            if request.content_type == "application/json":
                payload = await request.json()
            else:
                body = await request.text()
                payload = _parse_kopia_plain_text(body)
        except Exception as err:
            _LOGGER.error("Error decoding Kopia webhook payload: %s", err)
            return web.Response(status=400, text="Invalid payload format")

        if not payload:
            return web.Response(status=400, text="Empty payload")

        coordinator_instance.update_data(payload)
        return web.Response(status=200, text="OK")

    try:
        async_register(hass, DOMAIN, "Kopia", webhook_id, handle_webhook)
        webhook_url = async_generate_url(hass, webhook_id)
        _LOGGER.info("Kopia Webhook registered successfully. URL: %s", webhook_url)
    except ValueError:
        pass 

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    try:
        async_unregister(hass, entry.data["webhook_id"]) 
    except Exception:
        pass
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
