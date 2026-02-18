# Pending Documentation Updates

Gesammelte Aenderungen fuer architecture.md und ha-internals.md.
Werden bei Gelegenheit (Milestone, Deploy) eingearbeitet und dann geleert.

---

## ha-internals.md

### State-Listener auf externe Sensor-Entities

```python
from homeassistant.helpers.event import async_track_state_change_event

unsub = async_track_state_change_event(
    hass, [entity_id], callback_fn
)
entry.async_on_unload(unsub)  # sauber abmelden beim Entry-Unload
```

- Feuert sofort wenn eine andere Integration den State der Entity aendert
- Kein Polling -- rein event-basiert ueber HA-internen Event Bus
- `hass.states.async_set()` loest automatisch `state_changed` Event aus
- Kombinieren mit Safety-Polling (z.B. 5min) als Fallback empfohlen
- Callback muss `@callback` dekoriert sein; Coroutines via `hass.async_create_task()`

---

## architecture.md

### Datenfluss-Ergaenzung (Dexcom-Listener)

Im Abschnitt "Datenfluss" ergaenzen:

```
Dexcom-Sensor (HA) --state_changed Event--> Listener (__init__.py)
                                                --> coordinator.async_request_refresh() (sofort)
                   --5min Safety-Polling------> Coordinator._async_update_data()
```

Statt bisher nur:
```
Dexcom-Sensor (HA) --> Coordinator (60s Polling)
```
