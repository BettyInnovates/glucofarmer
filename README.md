# GlucoFarmer

Custom Home Assistant integration for preclinical CGM monitoring of diabetized pigs.

## Features

- **Per-pig profiles** linked to Dexcom CGM sensors
- **Glucose monitoring** with range status, data gap detection
- **Event logging** with timestamps for insulin (3+ types) and feedings (BE)
- **Presets** for one-click logging of routine events
- **Snack documentation** with reason tracking (emergency, intervention, etc.)
- **Error correction** via event deletion
- **Daily statistics** (TIR, TBR, TAR, data completeness, totals)
- **Alarms** with push notifications for critical values and data gaps
- **Daily email report** at midnight

## Installation

### Manual

1. Copy `custom_components/glucofarmer/` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings > Devices & Services > Add Integration > Search "GlucoFarmer"

### Setup

For each pig:
1. Add the integration (one config entry per pig)
2. Enter the pig name
3. Select the Dexcom glucose sensor
4. Select the Dexcom trend sensor

### Configure catalogs and presets

Go to Settings > Devices & Services > GlucoFarmer > Configure to manage:
- Insulin products (name + category)
- Feeding categories
- Presets (one-click event logging)

## Services

| Service | Description |
|---------|------------|
| `glucofarmer.log_insulin` | Log insulin administration (pig, product, IU, timestamp, note) |
| `glucofarmer.log_feeding` | Log feeding event (pig, BE, category, description, timestamp) |
| `glucofarmer.delete_event` | Delete a logged event by ID |

## Dashboard

Import `custom_components/glucofarmer/dashboard.yaml` into a Lovelace dashboard.
Replace `piggy_01` entity IDs with your actual pig names.

4 pages: Overview, Input, Statistics, Settings.

## Requirements

- Home Assistant 2024.1+
- Dexcom integration configured and running

## License

MIT
