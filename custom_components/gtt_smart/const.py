"""Constants for the GTT Smart integration."""

from datetime import timedelta

DOMAIN = "gtt_smart"

GTT_API_URL = (
    "https://www.gtt.to.it/cms/index.php"
    "?option=com_gtt&task=palina.getTransitiOld"
    "&realtime=true&get_param=value&palina={stop_id}"
)

CONF_STOP_ID = "stop_id"
CONF_NAME = "name"
CONF_LINE = "line"
CONF_DIRECTION = "direction"
CONF_MODE = "mode"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MATCH_WINDOW = "match_window"
CONF_MIN_MINUTES = "min_minutes_away"
CONF_EMPTY_STATE = "empty_state_text"
CONF_EMPTY_ATTR = "empty_attr_text"

MODE_SMART = "smart_merge"
MODE_RT_ONLY = "realtime_only"
MODE_PR_ONLY = "scheduled_only"

DEFAULT_MODE = MODE_SMART
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MATCH_WINDOW = 10
DEFAULT_MIN_MINUTES = 0
DEFAULT_EMPTY_STATE = "No upcoming bus"
DEFAULT_EMPTY_ATTR = "--"

REQUEST_TIMEOUT = 15
DEFAULT_UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)