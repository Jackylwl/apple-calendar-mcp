// Test-only backend. This file is never compiled into the shipped server and does not import EventKit.
// All titles, identifiers, and dates below are synthetic boundary-test fixtures.
import Foundation
final class CalendarSource {
    let scenario = ProcessInfo.processInfo.environment["CALENDAR_TEST_SCENARIO"] ?? "empty"
    func touch() {
        let state = ProcessInfo.processInfo.environment["LOCAL_APPLE_CALENDAR_HOME"]!
        FileManager.default.createFile(atPath: state + "/backend-called", contents: Data())
    }
    func authorization() -> [String: Any] { ["full_access": false] }
    func requestAccess() { fatalError("Tests must never request access") }
    func calendars() throws -> [[String: String]] {
        touch()
        if scenario == "denied" { throw Failure.message("CALENDAR_ACCESS_REQUIRED") }
        return [["id": "fixture", "title": "Test Calendar"]]
    }
    func events(ids: [String], query: Query) throws -> [EventRecord] {
        touch()
        if scenario == "denied" { throw Failure.message("CALENDAR_ACCESS_REQUIRED") }
        try requireSelectedCalendars(ids, available: ["fixture"])
        let hk = TimeZone(identifier: "Asia/Hong_Kong")!
        func event(_ title: String, _ start: String, _ end: String, allDay: Bool = false, zone: TimeZone? = nil) -> EventRecord {
            EventRecord(title: title, start: try! parseDate(start), end: try! parseDate(end), allDay: allDay, calendar: "Test Calendar", dayZone: zone ?? hk)
        }
        switch scenario {
        case "all-day":
            return [event("Inclusive", "2026-10-01T00:00:00+08:00", "2026-10-01T23:59:59+08:00", allDay: true),
                    event("Exclusive", "2026-10-01T00:00:00+08:00", "2026-10-02T00:00:00+08:00", allDay: true),
                    event("Multi", "2026-10-01T00:00:00+08:00", "2026-10-03T23:59:59+08:00", allDay: true)]
        case "dst":
            return [event("DST", "2026-11-01T00:00:00-04:00", "2026-11-01T23:59:59-05:00", allDay: true, zone: TimeZone(identifier: "America/New_York")!)]
        case "occurrences":
            // Represents separate occurrences returned by EventKit, not an independent recurrence engine.
            return [event("Sample meeting", "2026-10-01T10:00:00+08:00", "2026-10-01T11:00:00+08:00"),
                    event("Sample meeting", "2026-10-08T10:00:00+08:00", "2026-10-08T11:00:00+08:00"),
                    event("Ends at boundary", "2026-09-30T23:00:00+08:00", "2026-10-01T00:00:00+08:00"),
                    event("Starts at boundary", "2026-10-09T00:00:00+08:00", "2026-10-09T01:00:00+08:00"),
                    event("Point", "2026-10-01T00:00:00+08:00", "2026-10-01T00:00:00+08:00")]
        case "many":
            return (0..<502).map { event("Item \($0)", "2026-10-01T10:00:00+08:00", "2026-10-01T11:00:00+08:00") }
        default: return []
        }
    }
}
