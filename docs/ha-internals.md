# HA-Interna (Referenz)

Gesammelte Erkenntnisse ueber Home Assistant APIs die fuer GlucoFarmer relevant sind.

## LovelaceData Zugriff

`LovelaceData` ist ein Dataclass, KEIN Dict. Zugriff:
```python
from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import LOVELACE_DATA

lovelace_data = hass.data.get(LOVELACE_DATA)       # typisierter Key
dashboards = lovelace_data.dashboards               # dict[str|None, LovelaceConfig]
lovelace_data.resources                             # ResourceCollection
lovelace_data.yaml_dashboards                       # dict fuer YAML-Dashboards
```

## Dashboard erstellen

Kein `dashboards_collection` auf LovelaceData! Eigene Collection instanziieren:
```python
coll = lovelace_dashboard.DashboardsCollection(hass)
await coll.async_load()
await coll.async_create_item({
    "url_path": "x",
    "allow_single_word": True,  # noetig fuer "glucofarmer" (kein Bindestrich)
    "title": "X",
    ...
})
dashboard_config = lovelace_data.dashboards["x"]
await dashboard_config.async_save(config_dict)
```

## Store API

```python
from homeassistant.helpers.storage import Store
store = Store(hass, version=1, key="glucofarmer_events")
data = await store.async_load()  # None wenn leer
await store.async_save(data)
```

## Benachrichtigungen

```python
# persistent_notification (bleibt in HA UI sichtbar)
await hass.services.async_call(
    "persistent_notification", "create",
    {"title": "...", "message": "...", "notification_id": "unique_id"},
)

# notify (Push/E-Mail etc.)
await hass.services.async_call(
    "notify", "notify",
    {"title": "...", "message": "...", "data": {"priority": "critical"}},
)
```

## Entity Registry

```python
from homeassistant.helpers import entity_registry as er
registry = er.async_get(hass)
entries = er.async_entries_for_config_entry(registry, entry.entry_id)
# entry.entity_id, entry.unique_id, entry.translation_key
```
