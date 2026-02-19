# GlucoFarmer

Custom Home Assistant integration for monitoring multiple CGM sensors.
Designed to work with any CGM device that exposes a glucose value and trend sensor in Home Assistant — currently tested with the [Dexcom integration](https://www.home-assistant.io/integrations/dexcom/).

## Features

- **Multiple profiles** — each linked to its own CGM glucose and trend sensor
- **Glucose monitoring** — range status (5 zones), trend, data gap detection
- **Event logging** — insulin administration and feeding/carb events with custom timestamps
- **Presets** — one-click logging of routine events
- **Statistics** — time-in-range (5 zones), data completeness, daily totals
- **Alarms** — push notifications for critical values and data gaps, with priority levels
- **Daily report** — summary sent as a Home Assistant notification at midnight

## Requirements

- Home Assistant 2024.1+
- A CGM integration that provides a glucose value sensor and a trend sensor (e.g. [Dexcom](https://www.home-assistant.io/integrations/dexcom/))
- [apexcharts-card](https://github.com/RomRider/apexcharts-card) (HACS frontend card, for dashboard)

## Installation

### Via HACS (recommended)

Add this repository as a custom HACS repository, then install GlucoFarmer.

### Manual

1. Copy `custom_components/glucofarmer/` to your HA `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration > Search for GlucoFarmer

## Setup

Add one integration entry per monitored profile:

1. Settings > Devices & Services > Add Integration > GlucoFarmer
2. Enter a profile name
3. Select the glucose sensor entity
4. Select the trend sensor entity

Repeat for each additional profile.

## Configuration

Go to Settings > Devices & Services > GlucoFarmer > Configure to manage:

- Glucose thresholds (5-zone system: critical low / low / in-range / high / very high)
- Insulin products
- Feeding/carb categories
- Presets for one-click logging

## Dashboard

The dashboard is generated automatically on setup (4 tabs: Overview, Input, Statistics, Settings).

Requires `apexcharts-card` from HACS.

## License

MIT
