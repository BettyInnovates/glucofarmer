"""Constants for the GlucoFarmer integration."""

from homeassistant.const import Platform

DOMAIN = "glucofarmer"
PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SELECT, Platform.SENSOR, Platform.TEXT]

# Config keys
CONF_SUBJECT_NAME = "pig_name"
CONF_GLUCOSE_SENSOR = "glucose_sensor"
CONF_TREND_SENSOR = "trend_sensor"

# Options keys
CONF_INSULIN_PRODUCTS = "insulin_products"
CONF_FEEDING_CATEGORIES = "feeding_categories"
CONF_PRESETS = "presets"

# SMTP / E-Mail options (global -- nur in einer Subject-Entry konfigurieren)
CONF_SMTP_ENABLED = "smtp_enabled"
CONF_SMTP_HOST = "smtp_host"
CONF_SMTP_PORT = "smtp_port"
CONF_SMTP_ENCRYPTION = "smtp_encryption"
CONF_SMTP_SENDER = "smtp_sender"
CONF_SMTP_SENDER_NAME = "smtp_sender_name"
CONF_SMTP_USERNAME = "smtp_username"
CONF_SMTP_PASSWORD = "smtp_password"
CONF_SMTP_RECIPIENTS = "smtp_recipients"

# Default thresholds (mg/dL)
DEFAULT_CRITICAL_LOW_THRESHOLD = 55
DEFAULT_VERY_LOW_THRESHOLD = 100
DEFAULT_LOW_THRESHOLD = 200
DEFAULT_HIGH_THRESHOLD = 300
DEFAULT_VERY_HIGH_THRESHOLD = 400
DEFAULT_DATA_TIMEOUT = 20  # minutes

# Glucose status values
STATUS_NORMAL = "normal"
STATUS_LOW = "low"
STATUS_VERY_LOW = "very_low"
STATUS_HIGH = "high"
STATUS_VERY_HIGH = "very_high"
STATUS_CRITICAL_LOW = "critical_low"
STATUS_NO_DATA = "no_data"

# Default insulin products
DEFAULT_INSULIN_PRODUCTS: list[dict[str, str]] = [
    {"name": "NovoRapid", "category": "short"},
    {"name": "Lantus", "category": "long"},
    {"name": "Experimental-1", "category": "experimental"},
]

# Default feeding categories
DEFAULT_FEEDING_CATEGORIES: list[str] = [
    "breakfast",
    "dinner",
    "reward",
    "emergency_single",
    "emergency_double",
    "intervention",
    "other",
]

# Insulin categories
INSULIN_CATEGORY_SHORT = "short"
INSULIN_CATEGORY_LONG = "long"
INSULIN_CATEGORY_EXPERIMENTAL = "experimental"

# Event types
EVENT_TYPE_INSULIN = "insulin"
EVENT_TYPE_FEEDING = "feeding"

# Preset types
PRESET_TYPE_INSULIN = "insulin"
PRESET_TYPE_FEEDING = "feeding"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}_events"

# Services
SERVICE_LOG_INSULIN = "log_insulin"
SERVICE_LOG_FEEDING = "log_feeding"
SERVICE_DELETE_EVENT = "delete_event"
SERVICE_SEND_DAILY_REPORT = "send_daily_report"

# Attributes
ATTR_SUBJECT_NAME = "subject_name"
ATTR_PRODUCT = "product"
ATTR_AMOUNT = "amount"
ATTR_TIMESTAMP = "timestamp"
ATTR_NOTE = "note"
ATTR_CATEGORY = "category"
ATTR_DESCRIPTION = "description"
ATTR_EVENT_ID = "event_id"
ATTR_PRESET_NAME = "preset_name"
