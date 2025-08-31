import datetime

from config import  (CalendarEvent, CalendarEventID, EvenStatus, calendar,
                     GetDayCalendarEvents, CreateCalendarEvent, SearchCalendarEvents,
                     CancelCalendarEvent, RescheduleCalendarEvent, AddCalendarEventParticipants)
from fastapi import FastAPI

app = FastAPI()

@app.post("/get_day_calendar_events")
def get_day_calendar_events(req: GetDayCalendarEvents) -> list[CalendarEvent] | dict[str, str]:
    """Returns the appointments for the given `day`. Returns a list of dictionaries with informations about each meeting.

    :param day: The day for which to return the appointments. Must be in format YYYY-MM-DD.
    """
    try:
        date = datetime.datetime.strptime(req.day, "%Y-%m-%d")
        return calendar.get_by_day(date.date())
    except Exception as e:
        return {
            "error": str(e)
        }

@app.post("/create_calendar_event")
def create_calendar_event(
        req: CreateCalendarEvent
) -> CalendarEvent | dict[str, str]:
    """Creates a new calendar event with the given details and adds it to the calendar.
    It also sends an email to the participants with the event details.

    :param title: The title of the event.
    :param start_time: The start time of the event. Must be in format YYYY-MM-DD HH:MM.
    :param end_time: The end time of the event. Must be in format YYYY-MM-DD HH:MM.
    :param description: The description of the event.
    :param participants: The list of participants' email addresses. If `null`, no participants are set. The calendar owner's email address is always included..
    :param location: The location of the event. If `null`, no location is set.
    """
    try:
        parsed_start_time = datetime.datetime.strptime(req.start_time, "%Y-%m-%d %H:%M")
        parsed_end_time = datetime.datetime.strptime(req.end_time, "%Y-%m-%d %H:%M")
        if req.participants is None:
            participants = []
        else:
            participants = req.participants
        new_event = calendar.create_event(req.title, req.description, parsed_start_time, parsed_end_time, req.location, participants)
        return new_event
    except Exception as e:
        return {
            "error": str(e)
        }

@app.post("/search_calendar_events")
def search_calendar_events(
        req: SearchCalendarEvents
) -> list[CalendarEvent] | dict[str, str] :
    """Searches calendar events that match the given query in the tile or the description. If provided, filters events by date.

    :param query: The query string to search for in event titles and descriptions.
    :param date: The date for which to search events. Must be in format YYYY-MM-DD. If `null`, searches all events.
    """
    if req.date is not None:
        date_ = datetime.datetime.strptime(req.date, "%Y-%m-%d").date()
    else:
        date_ = None
    matches = calendar.search_events(req.query, date_)
    if len(matches) == 0:
        return {
            "error": "No events found. Try with a different query."
        }
    return matches

@app.get("/get_current_day")
def get_current_day() -> str:
    """Returns the current day in ISO format, e.g. '2022-01-01'.
    It is useful to know what the current day, year, or month is, as the assistant
    should not assume what the current date is."""
    return calendar.current_day.isoformat()

@app.post("/cancel_calendar_event")
def cancel_calendar_event(
        req: CancelCalendarEvent
) -> str | dict[str, str]:
    """Cancels the event with the given `event_id`. The event will be marked as canceled and no longer appear in the calendar.
    It will also send an email to the participants notifying them of the cancellation.

    :param event_id: The ID of the event to cancel.
    """
    try:
        calendar.cancel_event(CalendarEventID(req.event_id))
    except Exception as e:
        return {
            "error": str(e)
        }

    return f"Event with ID {req.event_id} has been canceled and participants have been notified."

@app.post("/reschedule_calendar_event")
def reschedule_calendar_event(
        req: RescheduleCalendarEvent
) -> CalendarEvent | dict[str, str]:
    """Reschedules the event with the given `event_id` to the new start and end times.
    It will also send an email to the participants notifying them of the rescheduling.

    :param event_id: The ID of the event to reschedule.
    :param new_start_time: The new start time of the event. Must be in format YYYY-MM-DD HH:MM.
    :param new_end_time: The new end time of the event. Must be in format YYYY-MM-DD HH:MM.
    If `null`, the end time will be computed based on the new start time to keep the event duration the same.
    """
    if req.new_end_time is not None:
        parsed_new_end_time = datetime.datetime.strptime(req.new_end_time, "%Y-%m-%d %H:%M")
    else:
        parsed_new_end_time = None
    try:
        calendar_event = calendar.reschedule_event(
            CalendarEventID(req.event_id),
            datetime.datetime.strptime(req.new_start_time, "%Y-%m-%d %H:%M"),
            parsed_new_end_time,
        )
    except Exception as e:
        return {
            "error": str(e)
        }
    return calendar_event

@app.post("/add_calendar_event_participants")
def add_calendar_event_participants(
        req: AddCalendarEventParticipants,
) -> CalendarEvent | dict[str, str]:
    """Adds the given `participants` to the event with the given `event_id`.
    It will also email the new participants notifying them of the event.

    :param event_id: The ID of the event to add participants to.
    :param participants: The list of participants' email addresses to add to the event.
    """
    try:
        calendar_event = calendar.add_participants(CalendarEventID(req.event_id), req.participants)
    except Exception as e:
        return {
            "error": str(e)
        }

    return calendar_event