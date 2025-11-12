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
"""Config flow for Kopia Webhook Status integration."""
from __future__ import annotations

import logging

import voluptuous as vol # Import vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Define the schema to prompt the user for the custom webhook ID AND the history limit
WEBHOOK_ID_SCHEMA = vol.Schema({
    vol.Required("webhook_id"): str,
    # New field for the number of snapshots to track
    vol.Required("history_limit", default=10): vol.All(
        vol.Coerce(int), vol.Range(min=5, max=40)
    ),
})


class KopiaWebhookConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kopia Webhook Status."""

    VERSION = 2 # Increment version since configuration options changed

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            webhook_id = user_input["webhook_id"].lower() 
            
            # Simple validation for webhook ID format
            if not webhook_id or not webhook_id.isalnum() and "_" not in webhook_id:
                 errors["webhook_id"] = "invalid_format"
            
            # History limit validation is handled by vol.All(vol.Coerce(int), vol.Range(min=5, max=40))

            if not errors:
                # Create the entry, storing the user-provided webhook ID and history limit
                return self.async_create_entry(
                    title=f"Kopia Status ({webhook_id})",
                    data={
                        "webhook_id": webhook_id, 
                        "history_limit": user_input["history_limit"] # Store the new limit
                    },
                )
        
        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=WEBHOOK_ID_SCHEMA,
            errors=errors,
            description_placeholders={
                "instructions": (
                    "Enter the desired unique ID for the webhook URL, and the number of "
                    "past snapshots to track (5-40)."
                )
            },
        )
