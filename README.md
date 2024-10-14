# Calendar Merger

## Purpose

Calendar Merger is an application designed to simplify schedule management for professionals with complex timetables. It aggregates multiple calendars (e.g. personal and work) into a single "busy-time" calendar, providing a unified view of availability without compromising privacy. This tool eliminates the need for others to check multiple calendars, offering an easy way for people to book meetings while respecting the user's private schedule details.

## Features

- **Multi-calendar aggregation**: Merges events from multiple sources into a unified calendar.
- **Privacy-focused**: Converts all events to "Busy" status, protecting schedule details.
- **Flexible calendar sources**: Supports both remote URLs and local files for calendar input.
- **Timezone handling**: Normalizes all events to a specified local timezone.
- **Event filtering**: Considers event status (busy, free, tentative, OOO) and filters out events marked as "free".
- **Performance optimized**: Utilizes concurrent processing for faster calendar fetching and merging.
- **Caching**: Implements TTL caching for improved performance on frequently accessed remote calendars.
- **Overlapping event consolidation**: Merges overlapping events into single busy blocks.
- **Long event handling**: Splits events longer than 24 hours into separate chunks for better visualization in some web calendars, such as Google Calendar.

## Configuration Options

- `calendar_urls`: List of URLs or file paths for calendars to be merged
- `cache_expiration_minutes`: Duration for which remote calendar data is cached
- `local_timezone`: The timezone to which all events will be normalized
- `days_limit`: Number of days into the future for which events are processed
- `merge_overlapping_events`: Consolidates overlapping events into single busy blocks
- `event_splitting_strategy`: Determines how to handle events longer than 24 hours. Possible values:
  - `split`: Split events into 24 hours chunks
  - `split_and_adjust`: Split events into 24 hours chunks, but shorten the chunks by 1 minute (23 hours and 59 minutes), to overcome visualization issues with some web calendars
  - `no_split`: Do not split events
- `calendar_name`: Name of the merged calendar
- `busy_events_summary`: Summary text for busy events

## Environment Variables

- `CALENDAR_URLS`: JSON-formatted string of calendar URLs, useful for secure deployment on platforms like Replit.

## Usage

1. Set up your `config.yaml` file with your calendar URLs and preferences.
2. Run the application:

```bash
python calendar_merger.py
```

3. Access the merged calendar at `http://localhost:8000/calendar`

## Deployment

This application can be easily deployed on free tiers of various cloud services such as Replit, Google Cloud Functions, or AWS Lambda. Here's an example of deploying on Replit and using Google Calendar as a web front-end:

1. Host the application on Replit:
   - Create a new Repl and upload the application code.
   - Set up your calendar URLs securely in Repl secrets.
   - Ensure the Repl is set to run continuously.

2. Integrate with Google Calendar:
   - In Google Calendar, go to "Other calendars" and select "From URL".
   - Enter the URL of your Replit-hosted calendar (e.g., `https://your-repl-hostname.com/calendar`).
   - When importing, make sure to check "Make the calendar publicly accessible".

3. Share your availability:
   - In Google Calendar settings, find the "Public URL to this calendar" for the imported calendar.
   - Share this public URL with others to show your availability without revealing details of your original calendars.

## Visualization Hints

- **Open Web Calendar**: Consider using [Open Web Calendar](https://github.com/niccokunzmann/open-web-calendar) as an alternative to Google Calendar for enhanced calendar visualization and interaction.

- **Dummy calendar for hard boundaries**: Create a dummy calendar with two repeating "busy" events to establish clear availability boundaries:
  1. A daily repeating event from end-of-office hours to start-of-office hours the next morning (e.g., 6 PM to 9 AM).
  2. A weekly repeating event covering the entire weekend.

  This approach effectively blocks out your personal time, preventing meetings from being scheduled during off-hours or weekends. It's particularly useful when collaborating across different time zones, ensuring that no meetings are scheduled in the middle of the night.