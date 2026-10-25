# OpoMeteo for Home Assistant

Home Assistant integration for the [OpoMeteo](https://github.com/vefilippo/opossum-meteo-ha) weather station server. It reads the stations of your OpoMeteo server through its key-protected API and exposes each one as a device with sensors.

## Features

- One device per selected station, with entities created only for what the station actually measures.
- Online/offline status; when a station goes silent its measures become unavailable instead of showing stale values.
- Station position on the Home Assistant map (from the station's latitude and longitude).
- Choose which stations to add, optionally add new stations automatically, and pick the units.
- English and Italian translations.

## Installation (HACS)

1. In HACS open the menu, choose **Custom repositories** and add `https://github.com/vefilippo/opossum-meteo-ha` with category **Integration**.
2. Install **OpoMeteo** and restart Home Assistant.

## Setup

1. In the OpoMeteo web admin open **API keys** ("Chiavi API"), create a key and copy it (it is shown only once).
2. In Home Assistant go to **Settings > Devices & services > Add integration > OpoMeteo**.
3. Enter the OpoMeteo web address (for example `https://meteo.example.com`) and the key.
4. Tick the stations to add.

## Options

Open the integration and choose **Configure**:

| Option | Meaning |
| --- | --- |
| Stations | Stations added to Home Assistant. Unticking one removes its device and entities. |
| Add new stations automatically | New stations on the server are added on the next refresh. When off, a repair issue tells you a new station is available so you can tick it. A station you unticked is never added again by this option. |
| Units | `Home Assistant default` follows your system units; `Metric` forces degC, hPa, mm, mm/h; `Imperial` forces degF, inHg, in, in/h. You can still override a single entity in its own settings. |
| Update interval | Polling interval in seconds (default 60, minimum 30). |

## Entities

Sensors (only those the station supports):

| Entity | Notes |
| --- | --- |
| Temperature | |
| Humidity | |
| Pressure | Sea level when the station has an altitude, otherwise station pressure; attribute `pressure_kind` tells which. |
| Rain today | Resets daily. |
| Rain rate | |
| Battery | Battery-powered stations only. |
| Last reading | Diagnostic timestamp. |
| Battery voltage | Diagnostic, disabled by default. |
| Signal strength | Diagnostic (dBm), disabled by default. |

Binary sensors:

| Entity | Notes |
| --- | --- |
| Online | Connectivity; carries `latitude` / `longitude` so the station shows on the map. Always available while the server answers. |
| Storm | Storm detected. |
| Charging | Diagnostic, battery charging. |

## Troubleshooting

- **Invalid key / "re-authentication needed"**: the key was revoked or mistyped. Create a new one in the OpoMeteo admin and enter it in the re-authentication prompt Home Assistant shows.
- **Cannot connect**: use the address you open OpoMeteo with in a browser, reachable from the Home Assistant host.
- **Entities unavailable**: the station is offline (no reading within the server's silence threshold) or no longer on the server. They recover on their own with the next reading.
- **A station is missing**: it must be ticked in the options; with auto-add off, check Settings > Repairs.

## License

See [LICENSE](LICENSE).
