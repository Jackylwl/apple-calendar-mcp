import Foundation

let releaseVersion = "0.1.0"
enum Failure: Error { case message(String) }

func parseDate(_ value: Any?) throws -> Date {
    let invalid = Failure.message("INVALID_DATE: Use a valid RFC3339 timestamp with seconds and Z or an explicit offset; fractional seconds are optional.")
    guard let text = value as? String else { throw invalid }
    let regex = try NSRegularExpression(pattern: #"^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.([0-9]{1,9}))?(Z|[+-][0-9]{2}:[0-9]{2})$"#)
    guard let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)) else { throw invalid }
    func part(_ n: Int) -> String { Range(match.range(at: n), in: text).map { String(text[$0]) } ?? "" }
    let year = Int(part(1))!, month = Int(part(2))!, day = Int(part(3))!
    let hour = Int(part(4))!, minute = Int(part(5))!, second = Int(part(6))!
    let offset = part(8)
    var seconds = 0
    if offset != "Z" {
        let h = Int(offset.dropFirst().prefix(2))!, m = Int(offset.suffix(2))!
        guard h <= 23, m < 60 else { throw invalid }
        seconds = (h * 3600 + m * 60) * (offset.first == "-" ? -1 : 1)
    }
    guard year >= 1, (1...12).contains(month), (1...31).contains(day), hour < 24, minute < 60, second < 60,
          let zone = TimeZone(secondsFromGMT: seconds) else { throw invalid }
    var calendar = Calendar(identifier: .gregorian)
    calendar.timeZone = zone
    let components = DateComponents(year: year, month: month, day: day, hour: hour, minute: minute, second: second)
    guard let date = calendar.date(from: components) else { throw invalid }
    let actual = calendar.dateComponents([.year, .month, .day, .hour, .minute, .second], from: date)
    guard actual.year == year, actual.month == month, actual.day == day,
          actual.hour == hour, actual.minute == minute, actual.second == second else { throw invalid }
    return date.addingTimeInterval(Double("0." + part(7)) ?? 0)
}

struct Query {
    let start: Date
    let end: Date
    let zone: TimeZone
    let query: String?
    init(_ args: [String: Any], search: Bool) throws {
        start = try parseDate(args["start"])
        end = try parseDate(args["end"])
        guard end > start, end.timeIntervalSince(start) <= 31 * 86400 else {
            throw Failure.message("INVALID_RANGE: End must follow start; maximum elapsed range is 31 days. End is exclusive.")
        }
        guard let zone = TimeZone(identifier: args["timezone"] as? String ?? "Asia/Hong_Kong") else { throw Failure.message("INVALID_TIMEZONE") }
        self.zone = zone
        query = search ? (args["query"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines) : nil
        if query == "" { throw Failure.message("EMPTY_QUERY") }
    }
}

struct EventRecord {
    let title: String
    let start: Date
    let end: Date
    let allDay: Bool
    let calendar: String
    // All-day dates are civil dates in the event's zone, or the Mac's local zone for floating events.
    let dayZone: TimeZone
}

func dayString(_ date: Date, zone: TimeZone) -> String {
    let f = DateFormatter()
    f.locale = Locale(identifier: "en_US_POSIX")
    f.calendar = Calendar(identifier: .gregorian)
    f.timeZone = zone
    f.dateFormat = "yyyy-MM-dd"
    return f.string(from: date)
}

func allDayBounds(_ event: EventRecord, in zone: TimeZone) -> (Date, Date) {
    var source = Calendar(identifier: .gregorian)
    source.timeZone = event.dayZone
    let start = source.startOfDay(for: event.start)
    let endDay = source.startOfDay(for: event.end)
    // Preserve midnight-exclusive ends; round an inclusive/non-midnight end up to the next day.
    var end = event.end == endDay ? endDay : source.date(byAdding: .day, value: 1, to: endDay)!
    if end <= start { end = source.date(byAdding: .day, value: 1, to: start)! }
    var output = Calendar(identifier: .gregorian)
    output.timeZone = zone
    return (output.date(from: source.dateComponents([.year, .month, .day], from: start))!,
            output.date(from: source.dateComponents([.year, .month, .day], from: end))!)
}

func eventResult(_ records: [EventRecord], query: Query) -> [String: Any] {
    let matched = records.compactMap { event -> (EventRecord, Date, Date)? in
        let (start, end) = event.allDay ? allDayBounds(event, in: query.zone) : (event.start, event.end)
        let overlaps = start < query.end && (end > query.start || (end == start && start >= query.start))
        guard overlaps, query.query.map({ event.title.localizedCaseInsensitiveContains($0) }) ?? true else { return nil }
        return (event, start, end)
    }.sorted { a, b in
        if a.1 != b.1 { return a.1 < b.1 }
        if a.0.calendar != b.0.calendar { return a.0.calendar < b.0.calendar }
        return a.0.title < b.0.title
    }
    let f = ISO8601DateFormatter()
    f.timeZone = query.zone
    let rows: [[String: Any]] = matched.prefix(500).map { event, start, end in
        ["title": event.title, "start": event.allDay ? dayString(start, zone: query.zone) : f.string(from: start),
         "end": event.allDay ? dayString(end, zone: query.zone) : f.string(from: end),
         "all_day": event.allDay, "calendar": event.calendar]
    }
    return ["events": rows, "timezone": query.zone.identifier, "end_exclusive": true,
            "total_count": matched.count, "truncated": matched.count > 500,
            "queried_at": ISO8601DateFormatter().string(from: Date()),
            "source": "live EventKit query; account synchronization freshness is controlled by macOS"]
}

func allowedIDs(at path: URL) throws -> [String] {
    guard FileManager.default.fileExists(atPath: path.path) else {
        throw Failure.message("NO_CALENDARS_SELECTED: Configure allowed-calendars.json before reading events.")
    }
    let ids = try JSONDecoder().decode([String].self, from: Data(contentsOf: path))
    guard !ids.isEmpty else { throw Failure.message("NO_CALENDARS_SELECTED: Select calendar IDs from list_calendars first.") }
    guard ids.allSatisfy({ !$0.isEmpty }) else { throw Failure.message("INVALID_CALENDAR_SELECTION") }
    return Array(Set(ids))
}

func requireSelectedCalendars(_ ids: [String], available: [String]) throws {
    guard Set(ids).isSubset(of: Set(available)) else {
        throw Failure.message("CALENDAR_UNAVAILABLE: A selected calendar is missing. Select calendars again; no broader fallback was used.")
    }
}
