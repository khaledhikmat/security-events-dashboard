# Security Events Dashboard

A real-time dashboard for monitoring security system events from various sources (access control, incidents, monitoring, threats).

## Features

- Real-time event counters with auto-refresh every 5 seconds
- Filter events by source, type, and status (ingested/processed/skipped/outcome)
- Natural language query interface (simulated)
- Manual event creation
- Streaming mode toggle
- ~1000 simulated events with randomized data

## Technology Stack

- **Backend**: Python FastAPI
- **Frontend**: HTMX (server-side rendering, no React)
- **Styling**: Minimal CSS

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Application

### 1. Seed the Database (First Time or After Schema Changes)

Populate the database with 1000 sample events:
```bash
python seed.py
```

This will:
- Drop all existing events
- Create 1000 new random events with varied timestamps and processing states
- Display progress as events are created

**Note:** You need to run this manually - it's not automatic on server startup.

### 2. Start the Server

Start the FastAPI server:
```bash
python app.py
```

Or using uvicorn directly:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The dashboard will be available at: http://localhost:8000

## API Endpoints

### GET /api/events
Query events with filters:
- `source`: Filter by source type (All, access, incidents, monitoring, threat)
- `eventType`: Filter by event type
- `ingested`: Filter ingested events (true/false)
- `processed`: Filter processed events (true/false)
- `skipped`: Filter skipped events (true/false)
- `outcome`: Filter events with outcomes (true/false)

Returns event counts for overall, last 30 mins, last 15 mins, and last 5 mins.

### PUT /api/streaming
Toggle streaming mode:
- `mode`: on/off

### POST /api/query
Natural language query (simulated):
- `prompt`: Query text

Returns matching events in HTML table format.

### POST /api/events
Create manual event with sync or async processing:
- `mode`: sync/async (query parameter)
  - **async** (default): Returns immediately (201), processes event in background (3-8 seconds)
  - **sync**: Waits for processing to complete before returning (~7 seconds)
- Form data: source, event_type, sourceEntity, location, building, floor, wing, severity

**Background Processing:**
- Uses FastAPI's `BackgroundTasks` for async event processing
- Simulates API call delay of 3-8 seconds
- Updates event with `processedTimestamp`, `workflowStartTimestamp`, `workflowStopTimestamp`, and `outcome`
- Watch server logs to see background task completion messages

## Event Types

- **access**: admit, reject, door_held
- **incidents**: incident_created, incident_resolved
- **monitoring**: device_offline, device_online
- **threat**: detection_alert

## Locations

SAT, PHX, PLX, TMP, CHR, COL

## Severity Levels

LOW, MED, HIGH
