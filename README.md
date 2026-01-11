# microAQUA device integration

Home Assistant integration for **microAQUA** devices. It reads measurements from the controller, monitors alarms, and lets you control selected functions (for example, disabling regulation for a set time or muting the sound alarm).

## Features

- read core measurements (pH, temperatures, LED)
- control regulation (ON/OFF) with a configurable no‑regulation timer
- mute the sound alarm
- monitor alarm states and threshold parameters
- UI-based configuration (Config Flow)

## Requirements

- Home Assistant with HACS enabled (recommended) or manual installation
- microAQUA device reachable on the same network (TCP)
- device IP, port, and payload (from the microAQUA menu)

## Installation (HACS)

1. Add this repository to HACS as a **Custom Repository**.
2. Download the **microAQUA** integration in HACS.
3. Restart Home Assistant.
4. Go to **Settings → Devices & Services** and add **microAQUA**.

## Manual installation

1. Copy `custom_components/microaqua` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration in **Settings → Devices & Services**.

## Configuration

When adding the integration, provide:

- **Name** – display name in HA (default: `microAQUA`)
- **IP** – device IP address
- **Port** – TCP port (default: `7963`)
- **Payload** – data query payload (default: `TCPSCP?`)
- **Update interval** – refresh rate in seconds (default: `1`)
- **Timeout** – TCP connection timeout in seconds (default: `2`)
- **Data valid seconds** – time after which data is considered stale (default: `5`)

> The same parameters can be edited later in the integration options.

## Entities

The integration creates, among others:

**Sensors:**
- pH, temperatures 1–4, LED levels, last update time
- alarm states and threshold parameters (including temperature and pH alarms)
- additional status sensors (e.g., CO2/O2 sockets, fan controller)

**Switches:**
- **Regulation ON/OFF** – disable/enable regulation
- **Mute Sound Alarm** – silence the alarm

**Number:**
- **Set no‑regulation time** – minutes used when turning regulation back on

## Troubleshooting

If the integration cannot connect:

- verify IP/port/payload in the device menu
- ensure Home Assistant can reach the microAQUA on the network
- increase **Timeout** or **Update interval** if the network is unstable

## Support

Report issues and suggestions: [Issues](https://github.com/niwciu/microAQUA_HA_integration/issues)
