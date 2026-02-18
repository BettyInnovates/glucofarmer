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
    CONF_FEEDING_CATEGORIES,
    CONF_GLUCOSE_SENSOR,
    CONF_INSULIN_PRODUCTS,
    CONF_PIG_NAME,
    CONF_PRESETS,
    CONF_TREND_SENSOR,
    DEFAULT_FEEDING_CATEGORIES,
    DEFAULT_INSULIN_PRODUCTS,
    DOMAIN,
    INSULIN_CATEGORY_EXPERIMENTAL,
    INSULIN_CATEGORY_LONG,
    INSULIN_CATEGORY_SHORT,
)

_LOGGER = logging.getLogger(__name__)


def _get_dexcom_sensors(hass, device_class_filter: str | None = None) -> dict[str, str]:
    """Get a dict of entity_id -> friendly name for Dexcom sensor entities."""
    registry = er.async_get(hass)
    sensors: dict[str, str] = {}

    for entity in registry.entities.values():
        if entity.domain != "sensor":
            continue
        # Include Dexcom sensors and any sensor with glucose in name
        if entity.platform == "dexcom" or "glucose" in (entity.entity_id or ""):
            state = hass.states.get(entity.entity_id)
            name = (
                state.attributes.get("friendly_name", entity.entity_id)
                if state
                else entity.entity_id
            )
            sensors[entity.entity_id] = name

    # If no Dexcom sensors found, also include all sensor entities
    # so the user can pick any sensor
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
        """Handle the initial step: set up a pig profile."""
        errors: dict[str, str] = {}

        if user_input is not None:
            pig_name = user_input[CONF_PIG_NAME]

            # Check for duplicate pig name
            await self.async_set_unique_id(pig_name.lower().replace(" ", "_"))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=pig_name,
                data={
                    CONF_PIG_NAME: pig_name,
                    CONF_GLUCOSE_SENSOR: user_input[CONF_GLUCOSE_SENSOR],
                    CONF_TREND_SENSOR: user_input[CONF_TREND_SENSOR],
                },
                options={
                    CONF_INSULIN_PRODUCTS: DEFAULT_INSULIN_PRODUCTS,
                    CONF_FEEDING_CATEGORIES: DEFAULT_FEEDING_CATEGORIES,
                    CONF_PRESETS: [],
                },
            )

        sensors = _get_dexcom_sensors(self.hass)
        if not sensors:
            sensors = {"": "No sensors found"}

        sensor_list = list(sensors.keys())

        data_schema = vol.Schema(
            {
                vol.Required(CONF_PIG_NAME): str,
                vol.Required(CONF_GLUCOSE_SENSOR): vol.In(sensors),
                vol.Required(CONF_TREND_SENSOR): vol.In(sensors),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class GlucoFarmerOptionsFlow(OptionsFlow):
    """Handle options flow for GlucoFarmer (global catalogs + presets)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "manage_insulin_products",
                "manage_feeding_categories",
                "manage_presets",
            ],
        )

    # --- Insulin products ---

    async def async_step_manage_insulin_products(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage insulin products."""
        return self.async_show_menu(
            step_id="manage_insulin_products",
            menu_options=["add_insulin_product", "remove_insulin_product"],
        )

    async def async_step_add_insulin_product(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new insulin product."""
        if user_input is not None:
            products = list(
                self.config_entry.options.get(
                    CONF_INSULIN_PRODUCTS, DEFAULT_INSULIN_PRODUCTS
                )
            )
            products.append(
                {
                    "name": user_input["name"],
                    "category": user_input["category"],
                }
            )
            new_options = dict(self.config_entry.options)
            new_options[CONF_INSULIN_PRODUCTS] = products
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="add_insulin_product",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("category"): vol.In(
                        {
                            INSULIN_CATEGORY_SHORT: "Short-acting",
                            INSULIN_CATEGORY_LONG: "Long-acting",
                            INSULIN_CATEGORY_EXPERIMENTAL: "Experimental",
                        }
                    ),
                }
            ),
        )

    async def async_step_remove_insulin_product(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove an insulin product."""
        products = list(
            self.config_entry.options.get(
                CONF_INSULIN_PRODUCTS, DEFAULT_INSULIN_PRODUCTS
            )
        )

        if user_input is not None:
            name_to_remove = user_input["product"]
            products = [p for p in products if p["name"] != name_to_remove]
            new_options = dict(self.config_entry.options)
            new_options[CONF_INSULIN_PRODUCTS] = products
            return self.async_create_entry(title="", data=new_options)

        product_names = {p["name"]: p["name"] for p in products}
        if not product_names:
            return self.async_abort(reason="no_products")

        return self.async_show_form(
            step_id="remove_insulin_product",
            data_schema=vol.Schema(
                {vol.Required("product"): vol.In(product_names)}
            ),
        )

    # --- Feeding categories ---

    async def async_step_manage_feeding_categories(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage feeding categories."""
        return self.async_show_menu(
            step_id="manage_feeding_categories",
            menu_options=["add_feeding_category", "remove_feeding_category"],
        )

    async def async_step_add_feeding_category(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new feeding category."""
        if user_input is not None:
            categories = list(
                self.config_entry.options.get(
                    CONF_FEEDING_CATEGORIES, DEFAULT_FEEDING_CATEGORIES
                )
            )
            categories.append(user_input["category"])
            new_options = dict(self.config_entry.options)
            new_options[CONF_FEEDING_CATEGORIES] = categories
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="add_feeding_category",
            data_schema=vol.Schema({vol.Required("category"): str}),
        )

    async def async_step_remove_feeding_category(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a feeding category."""
        categories = list(
            self.config_entry.options.get(
                CONF_FEEDING_CATEGORIES, DEFAULT_FEEDING_CATEGORIES
            )
        )

        if user_input is not None:
            categories.remove(user_input["category"])
            new_options = dict(self.config_entry.options)
            new_options[CONF_FEEDING_CATEGORIES] = categories
            return self.async_create_entry(title="", data=new_options)

        cat_options = {c: c for c in categories}
        if not cat_options:
            return self.async_abort(reason="no_categories")

        return self.async_show_form(
            step_id="remove_feeding_category",
            data_schema=vol.Schema(
                {vol.Required("category"): vol.In(cat_options)}
            ),
        )

    # --- Presets ---

    async def async_step_manage_presets(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage presets."""
        return self.async_show_menu(
            step_id="manage_presets",
            menu_options=["add_preset", "remove_preset"],
        )

    async def async_step_add_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a new preset."""
        if user_input is not None:
            presets = list(self.config_entry.options.get(CONF_PRESETS, []))
            preset: dict[str, Any] = {
                "name": user_input["name"],
                "type": user_input["type"],
            }
            if user_input["type"] == "insulin":
                preset["product"] = user_input.get("product", "")
                preset["amount"] = user_input.get("amount", 0)
            else:
                preset["category"] = user_input.get("feeding_category", "")
                preset["amount"] = user_input.get("amount", 0)
            presets.append(preset)
            new_options = dict(self.config_entry.options)
            new_options[CONF_PRESETS] = presets
            return self.async_create_entry(title="", data=new_options)

        products = self.config_entry.options.get(
            CONF_INSULIN_PRODUCTS, DEFAULT_INSULIN_PRODUCTS
        )
        categories = self.config_entry.options.get(
            CONF_FEEDING_CATEGORIES, DEFAULT_FEEDING_CATEGORIES
        )

        product_names = [p["name"] for p in products]
        cat_options = list(categories)

        schema_dict: dict = {
            vol.Required("name"): TextSelector(),
            vol.Required("type"): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"value": "insulin", "label": "Insulin"},
                        {"value": "feeding", "label": "Feeding"},
                    ]
                )
            ),
            vol.Required("amount", default=1.0): NumberSelector(
                NumberSelectorConfig(min=0, step=0.5, mode=NumberSelectorMode.BOX)
            ),
        }
        if product_names:
            schema_dict[vol.Optional("product")] = SelectSelector(
                SelectSelectorConfig(options=product_names)
            )
        if cat_options:
            schema_dict[vol.Optional("feeding_category")] = SelectSelector(
                SelectSelectorConfig(options=cat_options)
            )

        return self.async_show_form(
            step_id="add_preset",
            data_schema=vol.Schema(schema_dict),
        )

    async def async_step_remove_preset(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove a preset."""
        presets = list(self.config_entry.options.get(CONF_PRESETS, []))

        if user_input is not None:
            name_to_remove = user_input["preset"]
            presets = [p for p in presets if p["name"] != name_to_remove]
            new_options = dict(self.config_entry.options)
            new_options[CONF_PRESETS] = presets
            return self.async_create_entry(title="", data=new_options)

        preset_names = {p["name"]: p["name"] for p in presets}
        if not preset_names:
            return self.async_abort(reason="no_presets")

        return self.async_show_form(
            step_id="remove_preset",
            data_schema=vol.Schema(
                {vol.Required("preset"): vol.In(preset_names)}
            ),
        )
