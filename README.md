# Kopia Webhook Status

## 💾 Monitor Your Kopia Backups in Home Assistant

The **Kopia Webhook Status** integration provides a sensor entity in Home Assistant that is updated immediately whenever a Kopia backup job completes.

Unlike polling-based solutions, this integration uses a **push-based webhook** to instantly receive the backup status, making it highly efficient and responsive. It also stores a full history of your recent backups as attributes on the sensor.

The integration supports **multiple Kopia instances**, allowing you to monitor several different backup jobs (e.g., separate machines or users) with unique sensor entities.

***

## Installation

### 1. Installation via HACS (Recommended)

HACS (Home Assistant Community Store) makes installation and updates simple. Since this is a new custom component, you must first add my repository to HACS.

1.  In Home Assistant, go to **HACS**.
2.  Go to the **Integrations** tab.
3.  Click the three dots **(⋮)** in the top right corner and select **Custom repositories**.
4.  Enter the URL: `https://github.com/SpaceFrags/kopia_webhook`
5.  Select **Integration** as the Category.
6.  Click **ADD**.
7.  After the repository is added, search for **"Kopia Webhook Status"** in the HACS Integrations section and click **Download**.
8.  **Restart Home Assistant** to load the new integration.

### 2. Manual Installation

1.  Download the latest release zip file from the [GitHub releases page](https://github.com/SpaceFrags/kopia_webhook/releases).
2.  Extract the contents. You should find a folder named `kopia_webhook`.
3.  Copy the entire `kopia_webhook` folder into your Home Assistant configuration directory under `custom_components/`.
    * **Resulting Path:** `config/custom_components/kopia_webhook/`
4.  **Restart Home Assistant** to load the new integration.

***

## Configuration

The configuration process involves two parts: setting up the integration in Home Assistant and then configuring Kopia to send the webhook data.

### Part 1: Home Assistant Setup

1.  In Home Assistant, navigate to **Settings** > **Devices & Services**.
2.  Click the **+ ADD INTEGRATION** button.
3.  Search for **"Kopia Webhook Status"**.
4.  You will be prompted to enter the following:
    * **Webhook ID:** A unique ID for this instance (e.g., `server_1_backup`). This ID will be part of the URL you use in Kopia.
    * **History Limit:** The number of past snapshots to track (between 5 and 40). The latest snapshot is the sensor's state, and the older ones are in the attributes.
5.  Click **SUBMIT**. The integration will be set up and display the full Webhook URL. **Copy this URL** for use in Kopia.

### Part 2: Kopia Webhook Profile Setup

You must configure Kopia to use the Home Assistant Webhook URL on successful backup completion.

1.  **Open Kopia UI** and go to **Settings** > **Maintenance**.
2.  Click on **Webhooks** (under Actions).
3.  Click **Add Profile**.
4.  Configure the new profile:
    * **Event:** Select **Successful Snapshot**.
    * **Method:** Select **POST**.
    * **URL:** Paste the full Webhook URL you copied from Home Assistant (e.g., `https://your-ha-url/api/webhook/server_1_backup`).
    * **Content Type:** Select **JSON** (this is important for Home Assistant to parse the payload correctly).
    * **Payload Template:** Kopia uses Go templates. Use the following simple template to send the necessary data:
        ```json
        {
          "path": "{{.SourcePath}}",
          "status": "{{.Status}}",
          "startTime": "{{.StartTime}}",
          "endTime": "{{.EndTime}}",
          "duration": "{{.Duration}}",
          "size": "{{.TotalSize}}",
          "files": "{{.Files}}",
          "directories": "{{.Directories}}",
          "error": "{{.Error}}"
        }
        ```
    * **Timeout:** (Optional) Keep the default or set a reasonable value.
5.  Click **Save**.

Your sensor will now update immediately after a successful Kopia snapshot is created.