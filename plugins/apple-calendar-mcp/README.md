# Apple Calendar MCP — Configuration

See the [project README](../../README.md) for installation, the demo and usage.

## Local state

First start compiles and signs the server, then installs it in:

```text
~/Library/Application Support/LocalAppleCalendar/
  calendar-mcp
  allowed-calendars.json
```

Startup never requests Calendar permission. Existing calendar selections are preserved. To rebuild after a source update, run `./scripts/setup.sh` from this plugin directory.

Set `LOCAL_APPLE_CALENDAR_HOME` consistently for the launcher and client to use another state directory.

## Authorization and selection

Check authorization without requesting access:

```sh
"$HOME/Library/Application Support/LocalAppleCalendar/calendar-mcp" --authorization-status
```

With your approval, request macOS Calendar Full Access:

```sh
"$HOME/Library/Application Support/LocalAppleCalendar/calendar-mcp" --request-access
```

Full Access includes OS-level write permission; the plugin implements only read operations. An assistant must obtain your approval before requesting access.

Use the `list_calendars` tool to obtain IDs. Save selected IDs as a JSON array in `allowed-calendars.json`. Missing or empty selections block event queries. Missing selected calendars cause an error. To select all current calendars, include every returned ID; new calendars are not added automatically.

## Tool arguments

| Tool | Arguments |
| --- | --- |
| `list_calendars` | None |
| `read_events` | `start`, `end`, optional `timezone` |
| `search_events` | `start`, `end`, `query`, optional `timezone` |

Dates must be RFC3339 timestamps with seconds and an explicit offset or `Z`. Fractional seconds are supported. Ranges use `[start, end)` and cannot exceed 31 elapsed days. Output defaults to `Asia/Hong_Kong` and accepts IANA time zones.

Search matches a case-insensitive substring in titles. All-day events preserve civil dates with an exclusive end date. EventKit supplies recurring occurrences. Responses include `total_count`, `truncated`, `timezone`, `end_exclusive` and `queried_at`. The query timestamp does not guarantee account synchronization freshness.

## Diagnostic client

Python 3.9+ is required only for the optional client, tests and packaging. From this plugin directory:

```sh
python3 server/client.py list_calendars
python3 server/client.py read_events \
  '{"start":"2026-01-01T00:00:00Z","end":"2026-01-02T00:00:00Z","timezone":"UTC"}'
```

## Troubleshooting

| Issue | Action |
| --- | --- |
| Swift compiler unavailable | Install Xcode Command Line Tools and restart the plugin. |
| First-start timeout | Check Codex's MCP startup log, then restart. You can run `./scripts/setup.sh` manually if compilation takes too long. |
| Build lock remains after a forced shutdown | Check that no build is running before removing `.first-build-lock` from the state directory. |
| `CALENDAR_ACCESS_REQUIRED` | Check authorization; request access only with your approval. |
| `NO_CALENDARS_SELECTED` | List calendars and save selected IDs. |
| `CALENDAR_UNAVAILABLE` | Update the selection after a calendar is removed or its ID changes. |
| `INVALID_DATE` / `INVALID_RANGE` | Supply valid timestamps and a range of at most 31 elapsed days. |
| `LOCAL_READ_FAILED` | Check that the selection file is readable and contains a JSON array of IDs. |
| Tools missing | Reload Codex and inspect plugin loading errors. Avoid duplicate MCP registrations. |

Tests simulate denied access and recurring occurrences; they do not validate every Calendar provider or Apple's synchronization behavior.
