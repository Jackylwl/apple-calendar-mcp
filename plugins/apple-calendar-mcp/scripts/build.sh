#!/bin/sh
set -eu
if ! xcrun --find swiftc >/dev/null 2>&1; then
  printf '%s\n' 'Swift compiler unavailable. Install Xcode Command Line Tools with xcode-select --install, then restart the plugin.' >&2
  exit 1
fi
calendar_plugin_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
calendar_output="${1:-$calendar_plugin_root/build/calendar-mcp}"
mkdir -p "$(dirname -- "$calendar_output")"
calendar_build_cache="$(mktemp -d "${TMPDIR:-/tmp}/calendar-mcp-build.XXXXXX")"
trap 'rm -rf -- "$calendar_build_cache"' EXIT HUP INT TERM
xcrun swiftc -O -target "$(uname -m)-apple-macosx14.0" -module-cache-path "$calendar_build_cache/modules" \
  "$calendar_plugin_root/server/CalendarCore.swift" "$calendar_plugin_root/server/CalendarMCP.swift" \
  "$calendar_plugin_root/server/EventKitSource.swift" -o "$calendar_build_cache/calendar-mcp" \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker "$calendar_plugin_root/server/Info.plist"
codesign --force --sign - --identifier local.codex.apple-calendar-readonly "$calendar_build_cache/calendar-mcp"
# Replace the executable only after compilation and signing both succeed.
cp "$calendar_build_cache/calendar-mcp" "$calendar_output.new"
mv -f "$calendar_output.new" "$calendar_output"
