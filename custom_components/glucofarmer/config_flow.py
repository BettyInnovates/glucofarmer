"""Config flow for GlucoFarmer."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .const import (
    CONF_GLUCOSE_SENSOR,
    CONF_INSULIN_TYPES,
    CONF_MEALS,
    CONF_SUBJECT_NAME,
    CONF_SUBJECT_WEIGHT_KG,
    CONF_TREND_SENSOR,
    DEFAULT_INSULIN_TYPES,
    DEFAULT_MEALS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _get_dexcom_sensors(hass, device_class_filter: str | None = None) -> dict[str, str]:
    """Get a dict of entity_id -> friendly name for Dexcom sensor entities."""
    registry = er.async_get(hass)
    sensors: dict[str, str] = {}

    for entity in registry.entities.values():
        if entity.domain != "sensor":
            continue
        if entity.platform == "dexcom" or "glucose" in (entity.entity_id or ""):
            state = hass.states.get(entity.entity_id)
            name = (
                state.attributes.get("friendly_name", entity.entity_id)
                if state
                else entity.entity_id
            )
            sensors[entity.entity_id] = name

    if not sensors:
        for state in hass.states.async_all("sensor"):
            name = state.attributes.get("friendly_name", state.entity_id)
            sensors[state.entity_id] = name

    return sensors


class GlucoFarmerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GlucoFarmer."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GlucoFarmerOptionsFlow:
        """Get the options flow handler."""
        return GlucoFarmerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: set up a subject profile."""
        errors: dict[str, str] = {}

        if user_input is not None:
            subject_name = user_input[CONF_SUBJECT_NAME]
            await self.async_set_unique_id(subject_name.lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=subject_name,
                data={
                    CONF_SUBJECT_NAME: subject_name,
                    CONF_GLUCOSE_SENSOR: user_input[CONF_GLUCOSE_SENSOR],
                    CONF_TREND_SENSOR: user_input[CONF_TREND_SENSOR],
                },
                options={
                    CONF_SUBJECT_WEIGHT_KG: user_input[CONF_SUBJECT_WEIGHT_KG],
                    CONF_MEALS: DEFAULT_MEALS,
                    CONF_INSULIN_TYPES: DEFAULT_INSULIN_TYPES,
                },
            )

        sensors = _get_dexcom_sensors(self.hass)
        if not sensors:
            sensors = {"": "No sensors found"}

        data_schema = vol.Schema(
            {
                vol.Required(CONF_SUBJECT_NAME): str,
                vol.Required(CONF_GLUCOSE_SENSOR): vol.In(sensors),
                vol.Required(CONF_TREND_SENSOR): vol.In(sensors),
                vol.Required(CONF_SUBJECT_WEIGHT_KG, default=5.0): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=200, step=0.1, mode=NumberSelectorMode.BOX)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class GlucoFarmerOptionsFlow(OptionsFlow):
    """Handle options flow for GlucoFarmer."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "manage_subject_profile",
                "manage_meals",
                "manage_insulin_types",
                "manage_email_settings",
            ],
        )

    # --- Subject profile (weight + sensors) ---

    async def async_step_manage_subject_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit subject profile: weight and sensor assignments."""
        if user_input is not None:
            new_options = dict(self.config_entry.options)
            new_options[CONF_SUBJECT_WEIGHT_KG] = user_input[CONF_SUBJECT_WEIGHT_KG]
            # Sensor changes update config entry data -- store in options as overrides
            new_data = dict(self.config_entry.data)
            new_data[CONF_GLUCOSE_SENSOR] = user_input[CONF_GLUCOSE_SENSOR]
            new_data[CONF_TREND_SENSOR] = user_input[CONF_TREND_SENSOR]
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data=new_options)

        sensors = _get_dexcom_sensors(self.hass)
        if not sensors:
            sensors = {"": "No sensors found"}

        cur = self.config_entry.options
        cur_data = self.config_entry.data
        return self.async_show_form(
            step_id="manage_subject_profile",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SUBJECT_WEIGHT_KG,
                        default=cur.get(CONF_SUBJECT_WEIGHT_KG, 5.0),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=0.1, max=200, step=0.1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_GLUCOSE_SENSOR,
                        default=cur_data.get(CONF_GLUCOSE_SENSOR, ""),
                    ): SelectSelector(SelectSelectorConfig(options=list(sensors.keys()))),
                    vol.Required(
                        CONF_TREND_SENSOR,
                        default=cur_data.get(CONF_TREND_SENSOR, ""),
                    ): SelectSelector(SelectSelectorConfig(options=list(sensors.keys()))),
                }
            ),
        )

    # --- Meals ---

    async def async_step_manage_meals(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage meal definitions."""
        return self.async_show_menu(
            step_id="manage_meals",
            menu_options=["add_meal", "remove_meal"],
        )

    async def async_step_add_meal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a meal definition (fixed BE or per-kg)."""
        if user_input is not None:
            meals = list(self.config_entry.options.get(CONF_MEALS, []))
            meal: dict[str, Any] = {"name": user_input["name"]}
            if user_input["mode"] == "per_kg":
                meal["be_per_kg"] = float(user_input["value"])
            else:
                meal["amount"] = float(user_input["value"])
            meals.append(meal)
            new_options = dict(self.config_entry.options)
            new_options[CONF_MEALS] = meals
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="add_meal",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): TextSelector(),
                    vol.Required("mode"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": "fixed", "label": "Fixed BE value"},
                                {"value": "per_kg", "label": "BE per kg (weight-based)"},
                            ]
                        )
                    ),
                    vol.Required("value", default=1.0): NumberSelector(
                        NumberSelectorConfig(
                            min=0, max=50, step=0.1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )

    async def async_step_remove_meal(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a meal definition."""
        meals = list(self.config_entry.options.get(CONF_MEALS, []))

        if user_input is not None:
            name_to_remove = user_input["meal"]
            meals = [m for m in meals if m["name"] != name_to_remove]
            new_options = dict(self.config_entry.options)
            new_options[CONF_MEALS] = meals
            return self.async_create_entry(title="", data=new_options)

        meal_names = {m["name"]: m["name"] for m in meals}
        if not meal_names:
            return self.async_abort(reason="no_meals")

        return self.async_show_form(
            step_id="remove_meal",
            data_schema=vol.Schema({vol.Required("meal"): vol.In(meal_names)}),
        )

    # --- Insulin types ---

    async def async_step_manage_insulin_types(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage insulin type names."""
        return self.async_show_menu(
            step_id="manage_insulin_types",
            menu_options=["add_insulin_type", "remove_insulin_type"],
        )

    async def async_step_add_insulin_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add an insulin type."""
        if user_input is not None:
            types = list(
                self.config_entry.options.get(CONF_INSULIN_TYPES, DEFAULT_INSULIN_TYPES)
            )
            new_type = user_input["name"].strip()
            if new_type and new_type not in types:
                types.append(new_type)
            new_options = dict(self.config_entry.options)
            new_options[CONF_INSULIN_TYPES] = types
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="add_insulin_type",
            data_schema=vol.Schema({vol.Required("name"): TextSelector()}),
        )

    async def async_step_remove_insulin_type(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove an insulin type."""
        types = list(
            self.config_entry.options.get(CONF_INSULIN_TYPES, DEFAULT_INSULIN_TYPES)
        )

        if user_input is not None:
            types = [t for t in types if t != user_input["type"]]
            new_options = dict(self.config_entry.options)
            new_options[CONF_INSULIN_TYPES] = types
            return self.async_create_entry(title="", data=new_options)

        type_options = {t: t for t in types}
        if not type_options:
            return self.async_abort(reason="no_insulin_types")

        return self.async_show_form(
            step_id="remove_insulin_type",
            data_schema=vol.Schema({vol.Required("type"): vol.In(type_options)}),
        )

    # --- E-Mail / SMTP ---

    async def async_step_manage_email_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage SMTP email settings for the daily report."""
        from homeassistant.helpers.selector import BooleanSelector, TextSelectorConfig, TextSelectorType

        if user_input is not None:
            new_options = dict(self.config_entry.options)
            new_options["smtp_enabled"] = user_input.get("smtp_enabled", False)
            new_options["smtp_host"] = user_input.get("smtp_host", "")
            new_options["smtp_port"] = int(user_input.get("smtp_port", 465))
            new_options["smtp_encryption"] = user_input.get("smtp_encryption", "tls")
            new_options["smtp_sender"] = user_input.get("smtp_sender", "")
            new_options["smtp_sender_name"] = user_input.get("smtp_sender_name", "GlucoFarmer")
            new_options["smtp_username"] = user_input.get("smtp_username", "")
            new_options["smtp_password"] = user_input.get("smtp_password", "")
            new_options["smtp_recipients"] = user_input.get("smtp_recipients", "")
            return self.async_create_entry(title="", data=new_options)

        from homeassistant.helpers.selector import BooleanSelector, TextSelectorConfig, TextSelectorType
        cur = self.config_entry.options
        return self.async_show_form(
            step_id="manage_email_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "smtp_enabled", default=cur.get("smtp_enabled", False)
                    ): BooleanSelector(),
                    vol.Optional(
                        "smtp_host", default=cur.get("smtp_host", "")
                    ): TextSelector(),
                    vol.Optional(
                        "smtp_port", default=cur.get("smtp_port", 465)
                    ): NumberSelector(
                        NumberSelectorConfig(min=1, max=65535, step=1, mode=NumberSelectorMode.BOX)
                    ),
                    vol.Optional(
                        "smtp_encryption", default=cur.get("smtp_encryption", "tls")
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": "tls", "label": "TLS (Port 465)"},
                                {"value": "starttls", "label": "STARTTLS (Port 587)"},
                            ]
                        )
                    ),
                    vol.Optional(
                        "smtp_sender", default=cur.get("smtp_sender", "")
                    ): TextSelector(),
                    vol.Optional(
                        "smtp_sender_name", default=cur.get("smtp_sender_name", "GlucoFarmer")
                    ): TextSelector(),
                    vol.Optional(
                        "smtp_username", default=cur.get("smtp_username", "")
                    ): TextSelector(),
                    vol.Optional(
                        "smtp_password", default=cur.get("smtp_password", "")
                    ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
                    vol.Optional(
                        "smtp_recipients", default=cur.get("smtp_recipients", "")
                    ): TextSelector(),
                }
            ),
        )
