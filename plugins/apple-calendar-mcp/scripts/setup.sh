#!/bin/sh
set -eu
umask 077
calendar_plugin_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
calendar_state="${LOCAL_APPLE_CALENDAR_HOME:-$HOME/Library/Application Support/LocalAppleCalendar}"
mkdir -p "$calendar_state"
"$calendar_plugin_root/scripts/build.sh" "$calendar_state/calendar-mcp"
if [ ! -e "$calendar_state/allowed-calendars.json" ]; then
  printf '[]\n' > "$calendar_state/allowed-calendars.json"
fi
printf 'Installed Calendar MCP %s in %s\n' '0.1.0' "$calendar_state"
printf '%s\n' 'No Calendar access was requested. See README.md for authorization and calendar selection.'
