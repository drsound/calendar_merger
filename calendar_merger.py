import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from threading import Lock
from typing import List

import icalendar
import pytz
import recurring_ical_events
import requests
import yaml
from cachetools import TTLCache
from flask import Flask, Response, abort
from icalendar import vDDDTypes

# Load configuration from config.yaml
with open('config.yaml', 'r') as config_file:
    config = yaml.safe_load(config_file)

# Use environment variable to override calendar URLs if provided
environment_calendar_urls = os.environ.get('CALENDAR_URLS')
if environment_calendar_urls:
    config['calendar_urls'] = json.loads(environment_calendar_urls)

# Initialize cache with a lock for thread-safe access
calendar_cache = TTLCache(
    maxsize=100,
    ttl=config['cache_expiration_minutes'] * 60
)
cache_access_lock = Lock()

app = Flask(__name__)


def fetch_and_extract_events(calendar_source: str) -> List[icalendar.Event]:
    """
    Retrieve and extract relevant events from a calendar source within the specified time range.

    Args:
        calendar_source: URL or local file path of the calendar.

    Returns:
        A list of extracted and normalized calendar events.

    Raises:
        HTTPException: If fetching a remote calendar fails.
        IOError: If reading a local calendar file fails.
    """
    raw_calendar_data = retrieve_calendar_data(calendar_source)
    calendar = icalendar.Calendar.from_ical(raw_calendar_data.decode('utf-8'))

    timezone = pytz.timezone(config['local_timezone'])
    range_start = datetime.now(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    range_end = range_start + timedelta(days=config['days_limit'])
    events_within_range = recurring_ical_events.of(calendar).between(range_start, range_end)

    # Filter out transparent events (events that do not block time)
    events_within_range = [event for event in events_within_range if event.get('transp', 'OPAQUE') == 'OPAQUE']

    # Normalize event times to the local timezone
    normalized_events = normalize_event_times(events_within_range)

    return normalized_events


def retrieve_calendar_data(calendar_source: str) -> bytes:
    """
    Fetch calendar data from a remote URL or local file, utilizing caching for remote sources.

    Args:
        calendar_source: URL or local file path of the calendar.

    Returns:
        Raw calendar data in bytes.

    Raises:
        HTTPException: If fetching a remote calendar fails.
    """
    if calendar_source.startswith('http'):
        with cache_access_lock:
            cached_data = calendar_cache.get(calendar_source)

        if cached_data:
            return cached_data
        else:
            response = requests.get(calendar_source)
            if response.status_code == 200:
                raw_data = response.content
                with cache_access_lock:
                    calendar_cache[calendar_source] = raw_data
                return raw_data
    else:
        with open(calendar_source, "rb") as file:
            return file.read()


def normalize_event_times(events: List[icalendar.Event]) -> List[icalendar.Event]:
    """
    Convert event start and end times to the target timezone.

    Args:
        events: List of calendar events.

    Returns:
        List of events with normalized start and end times.
    """
    timezone = pytz.timezone(config['local_timezone'])
    normalized = []
    for event in events:
        normalized_event = icalendar.Event()
        for time_attr in ['dtstart', 'dtend']:
            event_time = event.get(time_attr).dt
            if isinstance(event_time, datetime):
                event_time = event_time.astimezone(timezone)
            else:
                # Convert date to datetime at midnight in the target timezone
                event_time = timezone.localize(datetime.combine(event_time, datetime.min.time()))
            normalized_event[time_attr] = vDDDTypes(event_time)
        normalized.append(normalized_event)
    return normalized


def merge_all_calendars() -> bytes:
    """
    Aggregate events from all configured calendars into a single busy-time calendar.

    Returns:
        Merged calendar data in iCalendar format.
    """
    aggregated_events = []

    # Concurrently fetch and process all calendars for performance
    with ThreadPoolExecutor() as executor:
        future_to_source = {executor.submit(fetch_and_extract_events, url): url for url in config['calendar_urls']}
        for future in as_completed(future_to_source):
            aggregated_events.extend(future.result())

    # Optionally merge overlapping events
    if config['merge_overlapping_events']:
        aggregated_events = consolidate_overlapping_events(aggregated_events)

    # Optionally split events longer than 24 hours
    if config['event_splitting_strategy'] != 'no_split':
        aggregated_events = split_events_into_24h_chunks(aggregated_events)

    # Create a new iCalendar object with merged events marked as 'Busy'
    merged_calendar = icalendar.Calendar()
    merged_calendar.add('prodid', '-//Calendar Merger//EN')
    merged_calendar.add('version', '2.0')
    merged_calendar.add('x-wr-calname', config['calendar_name'])
    merged_calendar.add('x-wr-timezone', config['local_timezone'])
    for event in aggregated_events:
        event.add('summary', config['busy_events_summary'])
        merged_calendar.add_component(event)

    return merged_calendar.to_ical()


def consolidate_overlapping_events(events: List[icalendar.Event]) -> List[icalendar.Event]:
    """
    Merge events that overlap or are subsequent to create consolidated busy blocks.

    Args:
        events: List of calendar events.

    Returns:
        List of merged calendar events without overlaps.
    """
    # Sort events by start time for efficient merging
    sorted_events = sorted(events, key=lambda e: e.get('dtstart').dt)
    merged = []

    for event in sorted_events:
        if not merged or event.get('dtstart').dt > merged[-1].get('dtend').dt:
            merged.append(event)
        else:
            # Extend the end time of the last merged event if overlapping or subsequent
            new_end = max(merged[-1].get('dtend').dt, event.get('dtend').dt)
            merged[-1]['dtend'] = vDDDTypes(new_end)

    return merged


def split_events_into_24h_chunks(events: List[icalendar.Event]) -> List[icalendar.Event]:
    """
    Split events that span more than 24 hours into separate 24-hour chunks.

    Args:
        events: List of normalized calendar events.

    Returns:
        List of events split into 24-hour chunks, respecting the configured splitting strategy.
    """
    chunked_events = []
    for event in events:
        chunk_start = event.get('dtstart').dt
        event_end = event.get('dtend').dt

        while chunk_start < event_end:
            chunk = icalendar.Event()
            chunk['dtstart'] = vDDDTypes(chunk_start)

            next_chunk_start = chunk_start + timedelta(hours=24)
            if config['event_splitting_strategy'] == 'split_and_adjust':
                # Adjust end time to 23:59 from chunk start or the original end time, whichever is earlier
                chunk_end = min(chunk_start + timedelta(hours=23, minutes=59), event_end)
            else:
                # Standard 'split' strategy: use 24 hours from chunk start or the original end time, whichever is earlier
                chunk_end = min(next_chunk_start, event_end)

            chunk['dtend'] = vDDDTypes(chunk_end)

            chunked_events.append(chunk)
            chunk_start = next_chunk_start

    return chunked_events


@app.route("/calendar")
def serve_merged_calendar(request):
    """
    API endpoint to retrieve the aggregated busy-time calendar in iCalendar format.

    Returns:
        iCalendar file as an attachment.

    Raises:
        HTTPException: If calendar merging fails.
    """
    try:
        return Response(
            merge_all_calendars(),
            mimetype="text/calendar",
            headers={
                "Content-Disposition": "attachment; filename=busy-times.ics"
            }
        )
    except Exception:
        abort(500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
