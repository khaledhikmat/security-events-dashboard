# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Security Events Dashboard** application built as a demo/prototype for monitoring security system events from various sources (access control, incidents, monitoring, threats).

**Key Characteristics:**
- Demo/prototype application with simulated data
- Uses in-memory storage (`List[dict]`) - no real database
- Generates ~1000 randomized events on startup
- Server-side rendering with HTMX (no React/frontend framework)
- FastAPI backend with Python

## Technology Stack

- **Backend**: Python FastAPI
- **Frontend**: HTMX for server-side rendering, minimal JavaScript
- **Styling**: Vanilla CSS (no frameworks)
- **Data Storage**: In-memory list of dictionaries (simulating a database)
- **Background Processing**: FastAPI's `BackgroundTasks` for async workflows

## Project Structure

```
/Users/khaled/github/event-platform-dashboard/
├── app.py                      # Main FastAPI application
├── templates/
│   ├── dashboard.html          # Main dashboard page
│   ├── counters.html          # HTMX partial for event counters
│   ├── recent_events.html     # HTMX partial for recent events table
│   └── query_results.html     # HTMX partial for query results
├── requirements.txt           # Python dependencies
├── run.sh                     # Quick start script
├── README.md                  # Project documentation
├── explorations.md            # Technical learning notes
└── brd.md                     # Business requirements document

No database files - everything is in-memory!
```

## Running the Application

### Start the Server:
```bash
# Option 1: Use the script
./run.sh

# Option 2: Manual start
source venv/bin/activate
python app.py

# Option 3: Using uvicorn directly
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The dashboard is available at: **http://localhost:8000**

### Install Dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Key API Endpoints

### GET /api/events
Query events with filters. Returns counts (overall, last 30/15/5 mins).

**Query Parameters:**
- `source`: All, access, incidents, monitoring, threat
- `eventType`: Varies by source (e.g., admit, reject, door_held for access)
- `ingested`, `processed`, `skipped`, `outcome`: boolean filters

### POST /api/events
Create manual event with sync or async processing.

**Query Parameters:**
- `mode`: `async` (default, returns immediately) or `sync` (waits 3-8 seconds)

**Form Data:** source, event_type, sourceEntity, location, building, floor, wing, severity

**Important:**
- **Async mode**: Returns immediately (201), processes event in background using `BackgroundTasks`
- **Sync mode**: Waits for processing to complete before returning (~7 seconds)
- Background processing simulates API call delay of 3-8 seconds
- Watch server logs for `[Background] Event <id> processed successfully` messages

### GET /components/counters
HTMX partial endpoint - returns HTML for counter cards.
**Auto-refreshes every 5 seconds** via HTMX polling.

### GET /components/recent-events
HTMX partial endpoint - returns HTML for recent 10 events table.
**Auto-refreshes every 5 seconds** via HTMX polling.

### POST /api/query
Natural language query (simulated - no real LLM, just keyword matching).
Returns HTML table of matching events.

## Important Code Patterns

### Why `events_db` is `List[dict]` not `List[Event]`

The `Event` Pydantic model (app.py:39-56) is used for **API validation**, not storage.

```python
events_db: List[dict] = []  # In-memory storage - easy to mutate
```

**Reason:** Easier mutation for background processing. With dicts, we can do:
```python
event["processedTimestamp"] = datetime.now().isoformat()  # Simple!
```

With Pydantic models, we'd need:
```python
event = event.copy(update={"processedTimestamp": ...})  # More verbose
```

For production, you'd use SQLAlchemy ORM with a real database. See `explorations.md` for details.

### Background Task Processing

Uses FastAPI's `BackgroundTasks` for async event processing:

```python
async def process_event_workflow(event_id: str):
    """Simulates API call with 3-8 second delay"""
    await asyncio.sleep(random.uniform(3, 8))
    # Update event with processing results

@app.post("/api/events")
async def create_event(background_tasks: BackgroundTasks, mode: str = "async", ...):
    if mode == "async":
        background_tasks.add_task(process_event_workflow, event["id"])
    else:
        await process_event_workflow(event["id"])  # Sync mode
```

**Key Points:**
- `BackgroundTasks` is perfect for I/O-bound operations (API calls)
- Returns immediately in async mode
- Processes in background without blocking other requests
- See `explorations.md` for comparison with other approaches (Celery, asyncio.create_task, etc.)

### HTMX Polling Pattern

The dashboard uses HTMX polling to auto-refresh counters and recent events every 5 seconds:

```html
<div id="counters-container"
     hx-get="/components/counters"
     hx-trigger="load, every 5s"
     hx-include="#filter-form">
```

**How it works:**
- `hx-get`: Endpoint to fetch fresh HTML
- `hx-trigger="load, every 5s"`: Trigger on page load AND every 5 seconds
- `hx-include="#filter-form"`: Include current filter values as query params
- HTMX swaps the returned HTML into the container

This creates real-time-like updates without WebSockets or SSE.

### Dynamic Counters with Randomization

Counters add ±10% variation to simulate real-time changes:

```python
base_count = len([e for e in events if datetime.fromisoformat(e["timestamp"]) >= cutoff])
variation = int(base_count * random.uniform(-0.1, 0.1))
return max(0, base_count + variation)
```

This makes the dashboard feel "alive" during the 5-second polling cycles.

## Event Types and Data Structure

### Sources and Event Types
```python
SOURCES = ["access", "incidents", "monitoring", "threat"]

EVENT_TYPES = {
    "access": ["admit", "reject", "door_held"],
    "incidents": ["incident_created", "incident_resolved"],
    "monitoring": ["device_offline", "device_online"],
    "threat": ["detection_alert"]
}
```

### Event Structure
Each event in `events_db` has:
- **Identity**: id, source, type, sourceEntity
- **Location**: location (SAT/PHX/etc), building, floor, wing
- **Timing**: timestamp, ingestionTimestamp, processedTimestamp, skippedTimestamp
- **Workflow**: workflowStartTimestamp, workflowStopTimestamp
- **Metadata**: severity (LOW/MED/HIGH), outcome (dict with immediate/shortTerm/longTerm actions)

## UI Features

### Create Manual Event Modal
- **Processing Mode Selector**: Radio buttons for Async vs Sync mode
- **Spinner Overlay**: Shows only for sync mode (3-8 second processing)
- **Form Validation**: All fields required, dynamic event type dropdown based on source
- **Auto-refresh**: Triggers counter and recent events refresh after submission

### Filters
- Source dropdown (with dynamic event type updates)
- Checkboxes: Ingested, Processed, Skipped, Outcome
- **Auto-triggers refresh** on any change (no submit button needed)

### Counter Cards
- 4 gradient cards showing: Overall, Last 30 Mins, Last 15 Mins, Last 5 Mins
- Auto-refreshes every 5 seconds
- Shows variation to simulate real-time changes

### Recent Events Table
- Shows last 10 events based on current filters
- Randomly samples from top 50 recent events to show variation
- Auto-refreshes every 5 seconds
- Color-coded status (Processed=green, Ingested=blue, Skipped=yellow, Pending=gray)

## Common Development Tasks

### Adding a New Filter
1. Update filter form in `templates/dashboard.html`
2. Add parameter to `get_events()` in `app.py`
3. Apply filter logic in the function
4. Update `get_counters()` and `get_recent_events()` to accept the parameter

### Modifying Event Generation
See `generate_events()` function in `app.py` (lines 83-118):
- Adjust `count` parameter to change number of events
- Modify randomization logic for timestamps, statuses, etc.
- Change probabilities for ingested/processed/skipped/outcome

### Changing Polling Interval
Update `hx-trigger` in dashboard.html:
- Counters: line 453 (`hx-trigger="load, every 5s"`)
- Recent events: line 462 (`hx-trigger="load, every 5s"`)

Change `5s` to desired interval (e.g., `10s`, `3s`)

## Important Notes

### No Database
- All data is in-memory and regenerated on server restart
- No SQLAlchemy, no migrations, no persistence
- Perfect for demo/prototype, not for production

### Simulated Natural Language Query
- POST /api/query does simple keyword matching
- No real LLM integration (no API keys needed)
- Searches for source, location, severity, entity in prompt
- Returns random subset of matching events

### Background Processing
- Uses `asyncio.sleep()` to simulate API call delay
- In production, replace with actual HTTP calls using `httpx`
- Logs show `[API] Event <id> created, scheduled for async processing`
- Then later: `[Background] Event <id> processed successfully`

### Mode Parameter
- Comes from **query string**, not form data
- `mode: str = "async"` in function signature means query param with default
- Form data uses `Form(...)` (e.g., `source: str = Form(...)`)

## Tips for Working with This Codebase

1. **Check server logs** to see background task processing messages
2. **Use browser DevTools Network tab** to see HTMX polling requests
3. **Event data structure** is flexible dict - easy to add fields for testing
4. **HTMX attributes** on HTML elements control most dynamic behavior
5. **JavaScript is minimal** - only for modal, filters, and spinner control
6. **No build step** - just edit HTML/CSS and refresh browser

## Reference Documents

- **README.md**: User-facing documentation, API endpoint details
- **explorations.md**: Technical deep-dive on Pydantic vs SQLAlchemy, ORM patterns
- **brd.md**: Original business requirements (use as spec reference)

## Current State (Latest Session)

### Recent Enhancements Made:
1. ✅ Fixed event type dropdown to update when source changes
2. ✅ Added randomized counter variations (±10%) for dynamic feel
3. ✅ Auto-refresh on filter changes
4. ✅ Added "Recent Events (Last 10)" card with auto-refresh
5. ✅ Implemented background task processing with BackgroundTasks
6. ✅ Added processing mode selector (Async/Sync) in modal
7. ✅ Added visual spinner overlay for sync mode processing

### Server is Currently Running:
- Background shell ID: `c8b873`
- Command: `source venv/bin/activate && python app.py`
- URL: http://localhost:8000

### If Server Needs Restart:
```bash
# Kill existing
# (Find shell ID with BashOutput tool if needed)

# Start new
source venv/bin/activate && python app.py
```

## Future Considerations (Not Implemented)

These are mentioned in BRD but not currently implemented:
- Real database (SQLite/PostgreSQL with SQLAlchemy)
- Actual LLM integration for natural language queries
- Golang implementation (only Python FastAPI exists)
- Real authentication/authorization
- Event persistence across restarts
- Streaming mode actually doing something (currently just a toggle)

For production, you'd want to:
- Replace `List[dict]` with SQLAlchemy ORM models
- Add proper database migrations (Alembic)
- Implement real auth (OAuth2, JWT)
- Use Celery or RQ for background jobs at scale
- Add proper logging, monitoring, error handling
- Consider using SQLModel instead of separate Pydantic + SQLAlchemy models
