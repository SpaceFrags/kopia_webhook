---
name: Kopia Webhook Status
default_values:
  config_flow:
    webhook_id: "Unique Webhook ID"
---

This is a push-based custom component that monitors Kopia backup status via a Webhook.

It provides a sensor entity that updates immediately upon Kopia's completion and stores the full backup history as attributes.