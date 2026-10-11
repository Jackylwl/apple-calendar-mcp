import Foundation
import EventKit

final class CalendarSource {
    private lazy var store = EKEventStore()
    func requireAccess() throws {
        guard EKEventStore.authorizationStatus(for: .event) == .fullAccess else {
            throw Failure.message("CALENDAR_ACCESS_REQUIRED: Full Access is missing or denied. Ask the user before running --request-access.")
        }
    }
    func authorization() -> [String: Any] {
        ["status": EKEventStore.authorizationStatus(for: .event).rawValue,
         "full_access": EKEventStore.authorizationStatus(for: .event) == .fullAccess]
    }
    func requestAccess() {
        store.requestFullAccessToEvents { granted, error in
            emit(["granted": granted, "error": error?.localizedDescription ?? ""])
            exit(granted ? 0 : 1)
        }
        RunLoop.main.run()
    }
    func calendars() throws -> [[String: String]] {
        try requireAccess()
        return store.calendars(for: .event).map { ["id": $0.calendarIdentifier, "title": $0.title] }
    }
    func events(ids: [String], query: Query) throws -> [EventRecord] {
        try requireAccess()
        let calendars = store.calendars(for: .event).filter { ids.contains($0.calendarIdentifier) }
        try requireSelectedCalendars(ids, available: calendars.map(\.calendarIdentifier))
        // Padding retrieves floating all-day dates across zone boundaries. Core applies exact requested bounds.
        let predicate = store.predicateForEvents(withStart: query.start.addingTimeInterval(-2 * 86400),
                                                end: query.end.addingTimeInterval(2 * 86400), calendars: calendars)
        return store.events(matching: predicate).map {
            EventRecord(title: $0.title ?? "", start: $0.startDate, end: $0.endDate,
                        allDay: $0.isAllDay, calendar: $0.calendar.title, dayZone: $0.timeZone ?? .current)
        }
    }
}
