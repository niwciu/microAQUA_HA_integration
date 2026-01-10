# microAQUA device integration

This Home Assistant integration connects to a microAQUA controller, reads its measurements,
and exposes them as sensors in Home Assistant.

## Features

- pH measurement
- Temperatures (4 sensors + alarm thresholds)
- LED output levels
- Last update time

## Installation

1. Add this repository to HACS as a custom repository.
2. Download the microAQUA integration in HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services** and add the **microAQUA** integration.
5. Provide the host/IP, port, and payload. These values are available in the microAQUA device menu.

## Configuration details

- **Host/IP**: IP address of the microAQUA controller.
- **Port**: TCP port configured on the controller.
- **Payload**: Command payload (default: `TCPSCP?`).
- **Name**: Friendly name for the device.

## Troubleshooting

- Verify the controller is reachable on the configured TCP port.
- If data does not update, check the payload matches the controller settings.
