"""Constants for the OpoMeteo integration."""

DOMAIN = "opossum_meteo"

CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_STATIONS = "stations"
CONF_AUTO_ADD = "auto_add"
CONF_UNITS = "units"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_AUTO_ADD = True
DEFAULT_UNITS = "ha"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30

UNITS = ["ha", "metric", "imperial"]
