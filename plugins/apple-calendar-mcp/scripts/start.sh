#!/bin/sh
set -eu
umask 077
calendar_plugin_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
calendar_state="${LOCAL_APPLE_CALENDAR_HOME:-$HOME/Library/Application Support/LocalAppleCalendar}"
if [ ! -x "$calendar_state/calendar-mcp" ]; then
  mkdir -p "$calendar_state"
  calendar_lock="$calendar_state/.first-build-lock"
  calendar_wait=0
  until mkdir "$calendar_lock" 2>/dev/null; do
    if [ -x "$calendar_state/calendar-mcp" ]; then
      exec "$calendar_state/calendar-mcp"
    fi
    calendar_wait=$((calendar_wait + 1))
    if [ "$calendar_wait" -ge 120 ]; then
      printf '%s\n' 'Calendar MCP first build is still locked. Check for a running compiler before removing the .first-build-lock directory from the state directory.' >&2
      exit 1
    fi
    sleep 1
  done
  trap 'rmdir "$calendar_lock"' EXIT
  trap 'exit 1' HUP INT TERM
  if [ ! -x "$calendar_state/calendar-mcp" ]; then
    printf '%s\n' 'Preparing Apple Calendar MCP for first use…' >&2
    # stdout belongs exclusively to the MCP protocol.
    "$calendar_plugin_root/scripts/setup.sh" >&2
  fi
  rmdir "$calendar_lock"
  trap - EXIT HUP INT TERM
fi
exec "$calendar_state/calendar-mcp"
