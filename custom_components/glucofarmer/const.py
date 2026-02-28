"""Constants for the GlucoFarmer integration."""

from homeassistant.const import Platform

DOMAIN = "glucofarmer"
PLATFORMS = [Platform.BUTTON, Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

# Config keys
CONF_SUBJECT_NAME = "pig_name"
CONF_GLUCOSE_SENSOR = "glucose_sensor"
CONF_TREND_SENSOR = "trend_sensor"

# Options keys
CONF_SUBJECT_WEIGHT_KG = "weight_kg"
CONF_MEALS = "meals"
CONF_INSULIN_TYPES = "insulin_types"

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

# Alarm options keys (per alarm type: critical / notification / off)
CONF_ALARM_CRITICAL_LOW = "alarm_critical_low"
CONF_ALARM_VERY_LOW = "alarm_very_low"
CONF_ALARM_LOW = "alarm_low"
CONF_ALARM_HIGH = "alarm_high"
CONF_ALARM_VERY_HIGH = "alarm_very_high"
CONF_ALARM_NO_DATA = "alarm_no_data"
CONF_ALARM_FALLING_QUICKLY = "alarm_falling_quickly"
CONF_ALARM_RISING_QUICKLY = "alarm_rising_quickly"
CONF_NOTIFY_TARGETS = "notify_targets"

# Alarm priority values
ALARM_PRIORITY_CRITICAL = "critical"
ALARM_PRIORITY_NOTIFICATION = "notification"
ALARM_PRIORITY_OFF = "off"

# Alarm defaults
DEFAULT_ALARM_CRITICAL_LOW = ALARM_PRIORITY_CRITICAL
DEFAULT_ALARM_VERY_LOW = ALARM_PRIORITY_CRITICAL
DEFAULT_ALARM_LOW = ALARM_PRIORITY_NOTIFICATION
DEFAULT_ALARM_HIGH = ALARM_PRIORITY_NOTIFICATION
DEFAULT_ALARM_VERY_HIGH = ALARM_PRIORITY_NOTIFICATION
DEFAULT_ALARM_NO_DATA = ALARM_PRIORITY_NOTIFICATION
DEFAULT_ALARM_FALLING_QUICKLY = ALARM_PRIORITY_CRITICAL
DEFAULT_ALARM_RISING_QUICKLY = ALARM_PRIORITY_NOTIFICATION
DEFAULT_NOTIFY_TARGETS = ""  # empty = notify.notify (broadcast to all devices)

# Default thresholds (mg/dL)
DEFAULT_CRITICAL_LOW_THRESHOLD = 55
DEFAULT_VERY_LOW_THRESHOLD = 100
DEFAULT_LOW_THRESHOLD = 200
DEFAULT_HIGH_THRESHOLD = 300
DEFAULT_VERY_HIGH_THRESHOLD = 400
# Glucose status values
STATUS_NORMAL = "normal"
STATUS_LOW = "low"
STATUS_VERY_LOW = "very_low"
STATUS_HIGH = "high"
STATUS_VERY_HIGH = "very_high"
STATUS_CRITICAL_LOW = "critical_low"
STATUS_NO_DATA = "no_data"

# Default meals (fallback -- user defines own meals via config flow)
DEFAULT_MEALS: list[dict] = []

# Default insulin types
DEFAULT_INSULIN_TYPES: list[str] = ["short-acting", "long-acting", "GSI"]

# Event types
EVENT_TYPE_INSULIN = "insulin"
EVENT_TYPE_FEEDING = "feeding"

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
ATTR_AMOUNT = "amount"
ATTR_TIMESTAMP = "timestamp"
ATTR_NOTE = "note"
ATTR_EVENT_ID = "event_id"
ATTR_PRODUCT = "product"
ATTR_CATEGORY = "category"
ATTR_DESCRIPTION = "description"
