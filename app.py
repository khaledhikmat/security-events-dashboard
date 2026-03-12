from fastapi import FastAPI, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import random
import asyncio

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Global state
streaming_mode = "on"
events_db: List[dict] = []

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


class Event(BaseModel):
    id: str
    source: str
    type: str
    sourceEntity: str
    timestamp: str
    location: str
    building: str
    floor: str
    wing: str
    severity: str
    ingestionTimestamp: Optional[str] = None
    processedTimestamp: Optional[str] = None
    skippedTimestamp: Optional[str] = None
    workflowStartTimestamp: Optional[str] = None
    workflowStopTimestamp: Optional[str] = None
    outcome: Optional[dict] = None


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


def generate_events(count=1000):
    """Generate simulated events"""
    global events_db
    events_db = []

    now = datetime.now()

    for i in range(count):
        source = random.choice(SOURCES)
        event_type = random.choice(EVENT_TYPES[source])

        # Random timestamp in the last 24 hours
        minutes_ago = random.randint(0, 1440)
        timestamp = now - timedelta(minutes=minutes_ago)

        # Determine if event was ingested/processed/skipped
        ingested = random.random() > 0.1  # 90% ingested
        processed = ingested and random.random() > 0.2  # 80% of ingested are processed
        skipped = ingested and not processed and random.random() > 0.5  # Some are skipped
        has_outcome = processed and random.random() > 0.3  # 70% of processed have outcomes

        event = {
            "id": str(uuid.uuid4()),
            "source": source,
            "type": event_type,
            "sourceEntity": random.choice(SOURCE_ENTITIES[source]),
            "timestamp": timestamp.isoformat(),
            "location": random.choice(LOCATIONS),
            "building": random.choice(BUILDINGS),
            "floor": random.choice(FLOORS),
            "wing": random.choice(WINGS),
            "severity": random.choice(SEVERITIES),
            "ingestionTimestamp": (timestamp + timedelta(seconds=random.randint(1, 5))).isoformat() if ingested else None,
            "processedTimestamp": (timestamp + timedelta(seconds=random.randint(10, 60))).isoformat() if processed else None,
            "skippedTimestamp": (timestamp + timedelta(seconds=random.randint(5, 30))).isoformat() if skipped else None,
            "workflowStartTimestamp": (timestamp + timedelta(seconds=random.randint(15, 70))).isoformat() if has_outcome else None,
            "workflowStopTimestamp": (timestamp + timedelta(seconds=random.randint(80, 180))).isoformat() if has_outcome else None,
            "outcome": generate_outcome() if has_outcome else None
        }

        events_db.append(event)


# Generate events on startup
generate_events(1000)


async def process_event_workflow(event_id: str):
    """
    Background task to simulate async event processing workflow.
    This simulates calling an external API that might take a few seconds.
    """
    # Simulate API call delay (3-8 seconds)
    await asyncio.sleep(random.uniform(3, 8))

    # Find the event and update it with processing results
    for event in events_db:
        if event["id"] == event_id:
            now = datetime.now()

            # Update processing timestamps
            event["processedTimestamp"] = now.isoformat()
            event["workflowStartTimestamp"] = (now - timedelta(seconds=random.randint(2, 5))).isoformat()
            event["workflowStopTimestamp"] = now.isoformat()

            # Generate outcome for the processed event
            event["outcome"] = generate_outcome()

            print(f"[Background] Event {event_id[:8]} processed successfully")
            break


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
    outcome: bool = False
):
    """Query events with filters and return counts"""
    filtered_events = events_db.copy()

    # Apply filters
    if source != "All":
        filtered_events = [e for e in filtered_events if e["source"] == source]

    if eventType != "All":
        filtered_events = [e for e in filtered_events if e["type"] == eventType]

    if ingested:
        filtered_events = [e for e in filtered_events if e["ingestionTimestamp"] is not None]

    if processed:
        filtered_events = [e for e in filtered_events if e["processedTimestamp"] is not None]

    if skipped:
        filtered_events = [e for e in filtered_events if e["skippedTimestamp"] is not None]

    if outcome:
        filtered_events = [e for e in filtered_events if e["outcome"] is not None]

    # Calculate time-based counts with some randomization to simulate real-time changes
    now = datetime.now()

    def count_in_timeframe(events, minutes):
        cutoff = now - timedelta(minutes=minutes)
        base_count = len([e for e in events if datetime.fromisoformat(e["timestamp"]) >= cutoff])
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
async def query_events(request: Request, prompt: str = Form(...)):
    """Natural language query (simulated)"""
    # Simulate query by returning random subset of events
    # In real implementation, this would use LLM to parse the query

    # Simple keyword matching for demo
    results = []
    prompt_lower = prompt.lower()

    for event in random.sample(events_db, min(50, len(events_db))):
        # Check if prompt mentions source, location, severity etc
        if (event["source"] in prompt_lower or
            event["location"] in prompt_lower or
            event["severity"] in prompt_lower or
            event["sourceEntity"].lower() in prompt_lower):
            results.append(event)

    # Return up to 10 results
    final_results = results[:10] if results else random.sample(events_db, min(10, len(events_db)))

    return templates.TemplateResponse("query_results.html", {
        "request": request,
        "results": final_results,
        "prompt": prompt
    })


@app.post("/api/events")
async def create_event(
    background_tasks: BackgroundTasks,
    mode: str = "async",
    source: str = Form(...),
    event_type: str = Form(...),
    sourceEntity: str = Form(...),
    location: str = Form(...),
    building: str = Form(...),
    floor: str = Form(...),
    wing: str = Form(...),
    severity: str = Form(...)
):
    """Create a new manual event"""
    now = datetime.now()

    event = {
        "id": str(uuid.uuid4()),
        "source": source,
        "type": event_type,
        "sourceEntity": sourceEntity,
        "timestamp": now.isoformat(),
        "location": location,
        "building": building,
        "floor": floor,
        "wing": wing,
        "severity": severity,
        "ingestionTimestamp": (now + timedelta(seconds=1)).isoformat(),
        "processedTimestamp": None,
        "skippedTimestamp": None,
        "workflowStartTimestamp": None,
        "workflowStopTimestamp": None,
        "outcome": None
    }

    # Insert event into database
    events_db.insert(0, event)

    # Handle sync vs async processing
    if mode == "sync":
        # Synchronous processing - process immediately before returning
        await process_event_workflow(event["id"])
    else:
        # Asynchronous processing - schedule background task
        background_tasks.add_task(process_event_workflow, event["id"])
        print(f"[API] Event {event['id'][:8]} created, scheduled for async processing")

    return {"status": "success", "event": event, "mode": mode}


@app.get("/components/counters", response_class=HTMLResponse)
async def get_counters(
    request: Request,
    source: str = "All",
    eventType: str = "All",
    ingested: bool = False,
    processed: bool = False,
    skipped: bool = False,
    outcome: bool = False
):
    """Return counter cards HTML for HTMX polling"""
    data = await get_events(source, eventType, ingested, processed, skipped, outcome)
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
    outcome: bool = False
):
    """Return recent events HTML for HTMX polling"""
    filtered_events = events_db.copy()

    # Apply filters
    if source != "All":
        filtered_events = [e for e in filtered_events if e["source"] == source]

    if eventType != "All":
        filtered_events = [e for e in filtered_events if e["type"] == eventType]

    if ingested:
        filtered_events = [e for e in filtered_events if e["ingestionTimestamp"] is not None]

    if processed:
        filtered_events = [e for e in filtered_events if e["processedTimestamp"] is not None]

    if skipped:
        filtered_events = [e for e in filtered_events if e["skippedTimestamp"] is not None]

    if outcome:
        filtered_events = [e for e in filtered_events if e["outcome"] is not None]

    # Sort by timestamp descending and get random 10 from recent events
    # To simulate real-time changes, shuffle a bit
    sorted_events = sorted(filtered_events, key=lambda x: x["timestamp"], reverse=True)

    # Take top 50 recent and randomly sample 10 to show variation
    recent_pool = sorted_events[:min(50, len(sorted_events))]
    recent_events = random.sample(recent_pool, min(10, len(recent_pool)))

    # Sort the selected 10 by timestamp again
    recent_events = sorted(recent_events, key=lambda x: x["timestamp"], reverse=True)

    return templates.TemplateResponse("recent_events.html", {
        "request": request,
        "events": recent_events
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
