from fastapi import FastAPI, Request, Form, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import random
import asyncio
import uuid
import httpx

import models
import schemas
from database import engine, get_db, Base, SessionLocal

# Create database tables on startup
Base.metadata.create_all(bind=engine)

# Global state
streaming_mode = "on"

# Type definitions
SOURCES = ["access", "incidents", "monitoring", "threat"]
EVENT_TYPES = {
    "access": ["admit", "reject", "door_held"],
    "incidents": ["incident_created", "incident_resolved"],
    "monitoring": ["device_offline", "device_online"],
    "threat": ["detection_alert"]
}
SOURCE_ENTITIES = {
    "access": ["Main Entrance", "Back Door", "Parking Gate", "Roof Access", "Server Room"],
    "incidents": ["INC-001", "INC-002", "INC-003", "INC-004", "INC-005"],
    "monitoring": ["Camera-A1", "Camera-B2", "Sensor-C3", "DVR-Main", "NVR-Backup"],
    "threat": ["Camera-North", "Camera-South", "Camera-East", "Camera-West", "Camera-Lobby"]
}
LOCATIONS = ["SAT", "PHX", "PLX", "TMP", "CHR", "COL"]
BUILDINGS = ["A", "B", "C", "D"]
FLOORS = ["1", "2", "3", "4"]
WINGS = ["E", "W", "N", "S"]
SEVERITIES = ["LOW", "MED", "HIGH"]


def generate_outcome():
    """Generate random outcome for an event"""
    actions = []
    for _ in range(random.randint(1, 2)):
        actions.append({
            "title": random.choice(["Lock Door", "Alert Security", "Review Footage", "Log Incident"]),
            "desc": random.choice(["Immediate action required", "Monitor situation", "Follow up needed"]),
            "triggerAccess": random.choice([True, False]),
            "triggerIncidents": random.choice([True, False]),
            "notifySecurity": random.choice([True, False])
        })

    return {
        "immediate": actions[:1] if actions else [],
        "shortTerm": actions[1:2] if len(actions) > 1 else [],
        "longTerm": []
    }


async def generate_and_insert_streaming_event(http_client: httpx.AsyncClient):
    """
    Generate a random event and insert into database for streaming mode.
    Then process it through the HTTP workflow.
    Creates a new database session for thread safety.
    """
    db = SessionLocal()
    try:
        # Generate random event data
        source = random.choice(SOURCES)
        event_type = random.choice(EVENT_TYPES[source])
        now = datetime.now()

        # Create event with only basic fields and ingestionTimestamp
        # Processing will be handled by process_event_workflow
        event = models.Event(
            id=str(uuid.uuid4()),
            source=source,
            type=event_type,
            sourceEntity=random.choice(SOURCE_ENTITIES[source]),
            timestamp=now,
            location=random.choice(LOCATIONS),
            building=random.choice(BUILDINGS),
            floor=random.choice(FLOORS),
            wing=random.choice(WINGS),
            severity=random.choice(SEVERITIES),
            ingestionTimestamp=now + timedelta(seconds=1)  # Set ingestion immediately
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        print(f"[Streaming] Generated event {event.id[:8]}... ({event.source}/{event.type})")

        # Close the DB session before HTTP workflow
        db.close()

        # Process event through HTTP workflow (will handle its own DB session)
        await process_event_workflow(event.id, http_client)

        return event.id

    except Exception as e:
        print(f"[Streaming] Error inserting event: {e}")
        db.rollback()
        return None
    finally:
        # Make sure DB is closed
        if db.is_active:
            db.close()


async def streaming_worker(http_client: httpx.AsyncClient):
    """
    Background worker that continuously generates events when streaming_mode is 'on'.
    Runs for the lifetime of the application.
    """
    print("[Streaming] Background worker started")

    try:
        while True:
            try:
                # Check if streaming is enabled
                if streaming_mode == "on":
                    # Generate and insert event
                    await generate_and_insert_streaming_event(http_client)
                else:
                    print("[Streaming] Mode is OFF, skipping event generation")

                # Wait random interval between 10 and 100 seconds
                delay = random.uniform(10, 100)
                print(f"[Streaming] Waiting {delay:.1f} seconds until next event...")
                await asyncio.sleep(delay)

            except asyncio.CancelledError:
                # Graceful shutdown requested
                print("[Streaming] Received shutdown signal")
                raise
            except Exception as e:
                print(f"[Streaming] Unexpected error in worker loop: {e}")
                # Continue loop even on errors, wait a bit before retrying
                await asyncio.sleep(5)

    except asyncio.CancelledError:
        print("[Streaming] Worker shutting down gracefully")
        raise  # Re-raise to properly exit


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Starts background streaming worker on startup, stops it on shutdown.
    Also creates a shared HTTP client for making API calls.
    """
    # Startup: Create HTTP client with connection pooling
    print("[HTTP] Creating shared HTTP client...")
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),  # 30s total, 5s connect
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=True
    )

    # Startup: Create background task
    print("[Streaming] Starting background event streaming...")
    task = asyncio.create_task(streaming_worker(app.state.http_client))

    yield  # Application runs here

    # Shutdown: Cancel background task
    print("[Streaming] Stopping background event streaming...")
    task.cancel()

    try:
        await asyncio.wait_for(task, timeout=5.0)
    except asyncio.TimeoutError:
        print("[Streaming] Worker didn't stop in time, forcing shutdown")
    except asyncio.CancelledError:
        print("[Streaming] Worker stopped successfully")

    # Shutdown: Close HTTP client
    print("[HTTP] Closing shared HTTP client...")
    await app.state.http_client.aclose()


# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


async def process_event_workflow(event_id: str, http_client: httpx.AsyncClient):
    """
    Background task to process event via external API call.
    Creates its own database session for thread safety.

    Args:
        event_id: ID of the event to process
        http_client: Shared HTTP client for making API requests
    """
    # Create new session for background task (thread-safe)
    db = SessionLocal()
    try:
        # Find the event
        event = db.query(models.Event).filter(models.Event.id == event_id).first()
        if not event:
            print(f"[Background] Event {event_id[:8]} not found")
            return

        # Prepare API request payload
        api_payload = {
            "event_id": event_id,
            "source": event.source,
            "type": event.type,
            "sourceEntity": event.sourceEntity,
            "timestamp": event.timestamp.isoformat(),
            "location": event.location,
            "building": event.building,
            "floor": event.floor,
            "wing": event.wing,
            "severity": event.severity
        }

        # Make HTTP POST request to external API
        # NOTE: Replace with your actual API endpoint
        api_url = "https://api.example.com/events/process"

        try:
            print(f"[HTTP] Calling API for event {event_id[:8]}...")
            response = await http_client.post(
                api_url,
                json=api_payload,
                timeout=30.0
            )
            response.raise_for_status()  # Raise exception for 4xx/5xx status codes

            # Parse API response
            api_result = response.json()
            print(f"[HTTP] API call successful for event {event_id[:8]}")

            # Update event with processing results from API
            now = datetime.now()
            event.processedTimestamp = now
            event.workflowStartTimestamp = now - timedelta(seconds=random.randint(2, 5))
            event.workflowStopTimestamp = now

            # Use outcome from API if provided, otherwise generate one
            event.outcome = api_result.get("outcome", generate_outcome())

            db.commit()
            print(f"[Background] Event {event_id[:8]} processed successfully")

        except httpx.TimeoutException as e:
            print(f"[HTTP] Timeout calling API for event {event_id[:8]}")
            # Mark event as errored due to timeout
            event.erroredTimestamp = datetime.now()
            event.errorType = "timeout"
            event.errorMessage = f"API request timed out after 30 seconds"
            db.commit()

        except httpx.HTTPStatusError as e:
            print(f"[HTTP] API returned error {e.response.status_code} for event {event_id[:8]}")
            # Mark event as errored due to HTTP error
            event.erroredTimestamp = datetime.now()
            event.errorType = "http_error"
            event.errorMessage = f"HTTP {e.response.status_code}: {e.response.text[:200] if hasattr(e.response, 'text') else 'Unknown error'}"
            db.commit()

        except httpx.RequestError as e:
            print(f"[HTTP] Network error calling API for event {event_id[:8]}: {e}")
            # Mark event as errored due to network error
            event.erroredTimestamp = datetime.now()
            event.errorType = "network_error"
            event.errorMessage = f"Network error: {str(e)[:200]}"
            db.commit()

    except Exception as e:
        print(f"[Background] Unexpected error processing event {event_id[:8]}: {e}")
        db.rollback()
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render main dashboard"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "streaming_mode": streaming_mode,
        "sources": SOURCES,
        "event_types": EVENT_TYPES
    })


@app.get("/api/events")
async def get_events(
    source: str = "All",
    eventType: str = "All",
    ingested: bool = False,
    processed: bool = False,
    skipped: bool = False,
    errored: bool = False,
    outcome: bool = False,
    db: Session = Depends(get_db)
):
    """Query events with filters and return counts"""
    # Build query with filters
    query = db.query(models.Event)

    if source != "All":
        query = query.filter(models.Event.source == source)

    if eventType != "All":
        query = query.filter(models.Event.type == eventType)

    if ingested:
        query = query.filter(models.Event.ingestionTimestamp.isnot(None))

    if processed:
        query = query.filter(models.Event.processedTimestamp.isnot(None))

    if skipped:
        query = query.filter(models.Event.skippedTimestamp.isnot(None))

    if errored:
        query = query.filter(models.Event.erroredTimestamp.isnot(None))

    if outcome:
        query = query.filter(models.Event.outcome.isnot(None))

    # Execute query to get all matching events
    filtered_events = query.all()

    # Calculate time-based counts with some randomization to simulate real-time changes
    now = datetime.now()

    def count_in_timeframe(events, minutes):
        cutoff = now - timedelta(minutes=minutes)
        base_count = len([e for e in events if e.timestamp >= cutoff])
        # Add small random variation (±10%) to simulate real-time changes
        variation = int(base_count * random.uniform(-0.1, 0.1))
        return max(0, base_count + variation)

    overall = len(filtered_events)
    # Add small variation to overall count too
    overall_variation = int(overall * random.uniform(-0.02, 0.02))
    overall = max(0, overall + overall_variation)

    return {
        "source": source,
        "streamingMode": streaming_mode,
        "eventType": eventType,
        "overall": overall,
        "last30Mins": count_in_timeframe(filtered_events, 30),
        "last15Mins": count_in_timeframe(filtered_events, 15),
        "last5Mins": count_in_timeframe(filtered_events, 5)
    }


@app.put("/api/streaming")
async def toggle_streaming(mode: str):
    """Toggle streaming mode on/off"""
    global streaming_mode
    streaming_mode = mode
    return {"status": "success"}


@app.post("/api/query", response_class=HTMLResponse)
async def query_events(request: Request, prompt: str = Form(...), db: Session = Depends(get_db)):
    """Natural language query (simulated)"""
    # Simulate query by returning random subset of events
    # In real implementation, this would use LLM to parse the query

    # Simple keyword matching for demo
    prompt_lower = prompt.lower()

    # Build query
    query = db.query(models.Event)

    # Apply simple keyword filters
    conditions = []
    for src in SOURCES:
        if src in prompt_lower:
            conditions.append(models.Event.source == src)

    for loc in LOCATIONS:
        if loc in prompt_lower:
            conditions.append(models.Event.location == loc)

    for sev in SEVERITIES:
        if sev.lower() in prompt_lower:
            conditions.append(models.Event.severity == sev)

    # Get sample results
    all_events = query.limit(100).all()
    results = random.sample(all_events, min(10, len(all_events))) if all_events else []

    return templates.TemplateResponse("query_results.html", {
        "request": request,
        "results": results,
        "prompt": prompt
    })


@app.get("/api/events/{event_id}")
async def get_event_by_id(event_id: str, db: Session = Depends(get_db)):
    """Get a single event by ID"""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        return {"error": "Event not found"}, 404
    return event


@app.post("/api/events")
async def create_event(
    request: Request,
    background_tasks: BackgroundTasks,
    mode: str = "async",
    source: str = Form(...),
    event_type: str = Form(...),
    sourceEntity: str = Form(...),
    location: str = Form(...),
    building: str = Form(...),
    floor: str = Form(...),
    wing: str = Form(...),
    severity: str = Form(...),
    db: Session = Depends(get_db)
):
    """Create a new manual event"""
    now = datetime.now()

    # Create SQLAlchemy model instance
    event = models.Event(
        source=source,
        type=event_type,
        sourceEntity=sourceEntity,
        timestamp=now,
        location=location,
        building=building,
        floor=floor,
        wing=wing,
        severity=severity,
        ingestionTimestamp=now + timedelta(seconds=1)
    )

    # Add to database and commit
    db.add(event)
    db.commit()
    db.refresh(event)

    # Get HTTP client from app state
    http_client = request.app.state.http_client

    # Handle sync vs async processing
    if mode == "sync":
        # Synchronous processing - process immediately before returning
        await process_event_workflow(event.id, http_client)
        # Refresh to get updated data
        db.refresh(event)
    else:
        # Asynchronous processing - schedule background task
        background_tasks.add_task(process_event_workflow, event.id, http_client)
        print(f"[API] Event {event.id[:8]} created, scheduled for async processing")

    return {"status": "success", "event": {"id": event.id}, "mode": mode}


@app.get("/components/counters", response_class=HTMLResponse)
async def get_counters(
    request: Request,
    source: str = "All",
    eventType: str = "All",
    ingested: bool = False,
    processed: bool = False,
    skipped: bool = False,
    errored: bool = False,
    outcome: bool = False,
    db: Session = Depends(get_db)
):
    """Return counter cards HTML for HTMX polling"""
    data = await get_events(source, eventType, ingested, processed, skipped, errored, outcome, db)
    return templates.TemplateResponse("counters.html", {
        "request": request,
        "data": data
    })


@app.get("/components/recent-events", response_class=HTMLResponse)
async def get_recent_events(
    request: Request,
    source: str = "All",
    eventType: str = "All",
    ingested: bool = False,
    processed: bool = False,
    skipped: bool = False,
    errored: bool = False,
    outcome: bool = False,
    db: Session = Depends(get_db)
):
    """Return recent events HTML for HTMX polling"""
    # Build query with filters
    query = db.query(models.Event)

    if source != "All":
        query = query.filter(models.Event.source == source)

    if eventType != "All":
        query = query.filter(models.Event.type == eventType)

    if ingested:
        query = query.filter(models.Event.ingestionTimestamp.isnot(None))

    if processed:
        query = query.filter(models.Event.processedTimestamp.isnot(None))

    if skipped:
        query = query.filter(models.Event.skippedTimestamp.isnot(None))

    if errored:
        query = query.filter(models.Event.erroredTimestamp.isnot(None))

    if outcome:
        query = query.filter(models.Event.outcome.isnot(None))

    # Get recent 10 events, ordered by timestamp descending
    recent_events = query.order_by(models.Event.timestamp.desc()).limit(10).all()

    return templates.TemplateResponse("recent_events.html", {
        "request": request,
        "events": recent_events
    })


@app.get("/components/event-detail/{event_id}", response_class=HTMLResponse)
async def get_event_detail(request: Request, event_id: str, db: Session = Depends(get_db)):
    """Return event detail modal HTML"""
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        return "<div>Event not found</div>"

    return templates.TemplateResponse("event_detail.html", {
        "request": request,
        "event": event
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
