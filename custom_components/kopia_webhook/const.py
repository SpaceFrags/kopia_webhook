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
"""Constants for the Kopia Webhook Status integration."""
# Domain name for the integration
DOMAIN = "kopia_webhook"
PLATFORMS = ["sensor"]

# Configuration keys
CONF_WEBHOOK_ID = "webhook_id"

# Kopia Payload Keys (Expected JSON keys from the webhook)
KOPIA_KEY_SOURCE_PATH = "sourcePath"
KOPIA_KEY_STATUS = "status"
KOPIA_KEY_END_TIME = "endTime"
KOPIA_KEY_DURATION = "duration"
KOPIA_KEY_SIZE = "size"
KOPIA_KEY_FILES = "files"
KOPIA_KEY_DIRS = "directories"
