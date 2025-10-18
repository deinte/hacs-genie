# Rituals Perfume Genie (HACS)

Custom Home Assistant integration for Rituals Perfume Genie diffusers, ready for installation via HACS.

## Features
- Automatic discovery of every Rituals diffuser linked to your Rituals account.
- Control fan power and perfume intensity, select room size presets.
- Diagnose diffuser state with cartridge, fill, battery, and Wi-Fi signal sensors.
- Handles the updated Rituals v2 cloud API with built-in token refresh logic.

## Requirements
- Home Assistant 2024.4.0 or newer.
- Rituals account credentials with at least one Perfume Genie diffuser assigned.
- HACS installed and configured with a GitHub Personal Access Token (PAT) if you access a private repository.

## Installation
1. In HACS open **Integrations → ⋮ → Custom repositories**, add the repository URL for this project, and choose `Integration`.
2. From the HACS store, open **Rituals Perfume Genie (HACS)** and install the latest version.
3. Restart Home Assistant (Settings → System → Restart) so the integration is loaded.

## Configuration
1. After the restart navigate to **Settings → Devices & Services → + Add Integration**.
2. Search for “Rituals Perfume Genie (HACS)” and select it.
3. Enter your Rituals email address and password. The integration validates your credentials against the v2 API and discovers all associated diffusers.
4. Newly created entities appear under the Rituals device. Rename or use them in automations as needed.

If you previously set up the built-in integration from Home Assistant Core, remove or disable that entry first to avoid duplicate entities.

## Troubleshooting
- **Integration missing from the add-in list**: confirm the files exist under `/config/custom_components/rituals_perfume_genie_hacs/`, reinstall from HACS if needed, and restart Home Assistant.
- **Authentication errors**: verify the Rituals credentials, or reauthenticate via **Settings → Devices & Services → Rituals Perfume Genie (HACS) → Configure**.
- **No entities created**: check **Settings → System → Logs** for entries tagged `rituals_perfume_genie` and file an issue with the log output.

## Notes
- The required `pyrituals` API client is vendored inside `custom_components/rituals_perfume_genie_hacs/pyrituals/`, so no external dependencies are downloaded at runtime.
- The polling interval is automatically adjusted to stay within Rituals’ cloud rate limits.

## Support
Please open an issue on the repository if you encounter bugs or have feature requests. Include debug logs when possible to speed up triage.
