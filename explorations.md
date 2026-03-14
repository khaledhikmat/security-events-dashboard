# Explorations and Learning Notes

This document captures technical discussions and explorations during the development of this project.

---

## Topic: Python Data Models - dict vs Pydantic vs SQLAlchemy ORM

### Question: Why is `events_db` a `List[dict]` instead of `List[Event]`?

**Current Implementation:**
```python
events_db: List[dict] = []  # In-memory storage
```

### Understanding Pydantic Models

The `Event` class in our app is a **Pydantic model**, which is primarily used for:
1. **API request/response validation** - Ensures data coming in/out of endpoints is correct
2. **Documentation** - Auto-generates OpenAPI/Swagger docs
3. **Type checking** - Provides IDE autocomplete and type hints

### Why Use `dict` for In-Memory Storage?

**Ease of Mutation:**
```python
# With dict - Simple and direct
event = events_db[0]
event["processedTimestamp"] = datetime.now().isoformat()  # ✅ Easy

# With Pydantic Event - More verbose
event = events_db[0]
event.processedTimestamp = datetime.now().isoformat()  # ⚠️ May fail if frozen
# Or need to recreate:
events_db[0] = event.copy(update={"processedTimestamp": ...})  # More code
```

### Comparison of Approaches

| Approach | Pros | Cons |
|----------|------|------|
| **`List[dict]`** (current) | Easy mutations, flexible, less memory overhead | No type safety, no validation, manual field checking |
| **`List[Event]`** (Pydantic) | Type safety, validation, IDE autocomplete | More verbose updates, slightly more memory |
| **Real database** (SQLAlchemy ORM) | Persistence, queries, relationships, proper data model | Requires DB setup, migrations |

### When to Use Each:

- **`List[dict]`**: In-memory demos, prototypes, simple data manipulation
- **`List[Event]`** (Pydantic): When you want type safety without a database
- **SQLAlchemy ORM**: Production apps with real persistence needs

---

## Topic: SQLAlchemy - Python's Standard ORM

### What is SQLAlchemy?

SQLAlchemy is **the most popular ORM (Object-Relational Mapping) library in Python**. It provides two main approaches:

### 1. ORM (Object-Relational Mapping) - High-Level

Maps Python classes to database tables:

```python
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

# Define ORM model
class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    type = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    severity = Column(String)
    processed_timestamp = Column(DateTime, nullable=True)

# Create database
engine = create_engine("sqlite:///events.db")
Base.metadata.create_all(engine)

# Use it
Session = sessionmaker(bind=engine)
session = Session()

# Create
event = Event(
    id=str(uuid.uuid4()),
    source="access",
    type="door_held",
    severity="HIGH"
)
session.add(event)
session.commit()

# Query
events = session.query(Event).filter(Event.source == "access").all()
```

### 2. Core (SQL Expression Language) - Lower-Level

Write SQL-like expressions in Python:

```python
from sqlalchemy import Table, Column, String, MetaData, select

metadata = MetaData()

events = Table('events', metadata,
    Column('id', String, primary_key=True),
    Column('source', String),
    Column('type', String),
)

# Execute queries
stmt = select(events).where(events.c.source == "access")
result = conn.execute(stmt)
```

---

## SQLAlchemy + FastAPI Pattern

### Typical File Structure:

```
app/
├── models.py       # SQLAlchemy ORM models (database layer)
├── schemas.py      # Pydantic models (API validation layer)
├── database.py     # Database connection setup
└── main.py         # FastAPI application
```

### Example Implementation:

**database.py** - Database Setup:
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./events.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

**models.py** - SQLAlchemy ORM Models:
```python
from sqlalchemy import Column, String, DateTime, JSON
from database import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True)
    source = Column(String, index=True)
    type = Column(String)
    sourceEntity = Column(String)
    timestamp = Column(DateTime)
    location = Column(String)
    severity = Column(String, index=True)
    outcome = Column(JSON, nullable=True)
    processed_timestamp = Column(DateTime, nullable=True)
```

**schemas.py** - Pydantic Models for API:
```python
from pydantic import BaseModel
from datetime import datetime

class EventCreate(BaseModel):
    source: str
    type: str
    sourceEntity: str
    location: str
    building: str
    floor: str
    wing: str
    severity: str

class EventResponse(BaseModel):
    id: str
    source: str
    type: str
    timestamp: datetime
    severity: str
    processed_timestamp: datetime | None

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy ORM objects
```

**main.py** - FastAPI Application:
```python
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import models, schemas
from database import SessionLocal, engine

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/api/events", response_model=schemas.EventResponse)
async def create_event(
    event: schemas.EventCreate,
    db: Session = Depends(get_db)
):
    # Create SQLAlchemy model instance
    db_event = models.Event(**event.dict(), id=str(uuid.uuid4()))
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event  # Pydantic converts it automatically

@app.get("/api/events")
async def get_events(
    source: str = "All",
    db: Session = Depends(get_db)
):
    query = db.query(models.Event)
    if source != "All":
        query = query.filter(models.Event.source == source)
    return query.all()
```

---

## Popular Python ORMs Comparison

| ORM | Description | Best For | Notes |
|-----|-------------|----------|-------|
| **SQLAlchemy** | Most mature, feature-rich, supports all major databases | Production apps, complex queries | Industry standard |
| **SQLModel** | Combines SQLAlchemy + Pydantic (by FastAPI author) | Modern FastAPI apps | Same model for DB and API |
| **Tortoise ORM** | Async-first, inspired by Django ORM | Async applications | Simpler API |
| **Django ORM** | Built into Django framework | Django projects | Excellent for Django apps |
| **Peewee** | Lightweight, simple API | Small apps, prototypes | Less features but easier |

---

## SQLModel - Modern Alternative (FastAPI + SQLAlchemy + Pydantic)

Created by the same author as FastAPI, **SQLModel** combines the best of both worlds:

```python
from sqlmodel import Field, SQLModel, create_engine, Session, select

# Single model class for BOTH database AND API validation!
class Event(SQLModel, table=True):
    id: str = Field(primary_key=True)
    source: str
    type: str
    severity: str
    timestamp: datetime
    processed_timestamp: datetime | None = None

# Create database
engine = create_engine("sqlite:///events.db")
SQLModel.metadata.create_all(engine)

# Use it
with Session(engine) as session:
    event = Event(
        id=str(uuid.uuid4()),
        source="access",
        type="door_held",
        severity="HIGH",
        timestamp=datetime.now()
    )
    session.add(event)
    session.commit()

    # Query
    statement = select(Event).where(Event.source == "access")
    results = session.exec(statement).all()
```

**Benefits of SQLModel:**
- Single model definition for database table AND API schema
- Full SQLAlchemy power under the hood
- Full Pydantic validation
- Less boilerplate code
- Type hints everywhere

---

## Topic: SQLAlchemy + SQLite Integration

### Does SQLAlchemy Work with SQLite?

**Yes! SQLAlchemy works excellently with SQLite.** In fact, SQLite is one of the most common databases used with SQLAlchemy.

### Why Use SQLite?

Perfect for:
- **Development/prototyping** - No separate database server needed
- **Small to medium applications** - Embedded database in a single file
- **Testing** - Fast, can use in-memory mode
- **Desktop applications** - Portable, single-file database

### Connection String Differences

The main difference across databases is just the connection string:

```python
# SQLite (file-based) - Creates events.db in current directory
engine = create_engine("sqlite:///./events.db")

# SQLite (in-memory) - Database resets on application restart
engine = create_engine("sqlite:///:memory:")

# PostgreSQL
engine = create_engine("postgresql://user:password@localhost/dbname")

# MySQL
engine = create_engine("mysql://user:password@localhost/dbname")
```

### Complete SQLite + SQLAlchemy Example

#### **database.py** - Database Connection
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite database file in current directory
SQLALCHEMY_DATABASE_URL = "sqlite:///./events.db"

# SQLite-specific: connect_args needed for thread safety with FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Only needed for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### **models.py** - SQLAlchemy ORM Models
```python
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.sql import func
from database import Base
import uuid

class Event(Base):
    __tablename__ = "events"

    # Primary key
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Core event fields
    source = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    sourceEntity = Column(String, nullable=False)

    # Location fields
    timestamp = Column(DateTime, nullable=False)
    location = Column(String, nullable=False)
    building = Column(String, nullable=False)
    floor = Column(String, nullable=False)
    wing = Column(String, nullable=False)
    severity = Column(String, nullable=False, index=True)

    # Nullable processing fields
    ingestionTimestamp = Column(DateTime, nullable=True)
    processedTimestamp = Column(DateTime, nullable=True)
    skippedTimestamp = Column(DateTime, nullable=True)
    workflowStartTimestamp = Column(DateTime, nullable=True)
    workflowStopTimestamp = Column(DateTime, nullable=True)

    # JSON column for outcome (SQLite supports JSON!)
    outcome = Column(JSON, nullable=True)

    # Auto-timestamp columns
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

#### **schemas.py** - Pydantic for API Validation
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any

class EventCreate(BaseModel):
    """Schema for creating new events via API"""
    source: str
    type: str
    sourceEntity: str
    timestamp: datetime
    location: str
    building: str
    floor: str
    wing: str
    severity: str

class EventResponse(BaseModel):
    """Schema for returning events from API"""
    id: str
    source: str
    type: str
    sourceEntity: str
    timestamp: datetime
    location: str
    building: str
    floor: str
    wing: str
    severity: str
    ingestionTimestamp: Optional[datetime] = None
    processedTimestamp: Optional[datetime] = None
    skippedTimestamp: Optional[datetime] = None
    workflowStartTimestamp: Optional[datetime] = None
    workflowStopTimestamp: Optional[datetime] = None
    outcome: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True  # Allows conversion from SQLAlchemy ORM objects
```

#### **app.py** - FastAPI with SQLite
```python
from fastapi import FastAPI, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio, random

import models, schemas
from database import engine, get_db, Base, SessionLocal

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Background processing (updated for SQLAlchemy)
async def process_event_workflow(event_id: str):
    """Process event asynchronously with new database session"""
    await asyncio.sleep(random.uniform(3, 8))

    # Create new session for background task (thread-safe)
    db = SessionLocal()
    try:
        event = db.query(models.Event).filter(models.Event.id == event_id).first()
        if event:
            now = datetime.now()
            event.processedTimestamp = now
            event.workflowStartTimestamp = now - timedelta(seconds=random.randint(2, 5))
            event.workflowStopTimestamp = now
            event.outcome = generate_outcome()

            db.commit()
            print(f"[Background] Event {event_id[:8]} processed successfully")
    finally:
        db.close()


@app.post("/api/events", response_model=schemas.EventResponse)
async def create_event(
    background_tasks: BackgroundTasks,
    event: schemas.EventCreate,
    mode: str = "async",
    db: Session = Depends(get_db)
):
    """Create a new event"""
    # Create SQLAlchemy model instance
    db_event = models.Event(
        **event.dict(),
        ingestionTimestamp=datetime.now()
    )

    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # Handle sync vs async processing
    if mode == "async":
        background_tasks.add_task(process_event_workflow, db_event.id)
    else:
        await process_event_workflow(db_event.id)

    return db_event


@app.get("/api/events")
async def get_events(
    source: str = "All",
    eventType: str = "All",
    ingested: bool = False,
    processed: bool = False,
    db: Session = Depends(get_db)
):
    """Query events with filters using SQLAlchemy"""
    query = db.query(models.Event)

    # Apply filters
    if source != "All":
        query = query.filter(models.Event.source == source)

    if eventType != "All":
        query = query.filter(models.Event.type == eventType)

    if ingested:
        query = query.filter(models.Event.ingestionTimestamp.isnot(None))

    if processed:
        query = query.filter(models.Event.processedTimestamp.isnot(None))

    # Execute query
    all_events = query.all()

    # Calculate counts
    now = datetime.now()
    overall = len(all_events)
    last30 = len([e for e in all_events if e.timestamp >= now - timedelta(minutes=30)])
    last15 = len([e for e in all_events if e.timestamp >= now - timedelta(minutes=15)])
    last5 = len([e for e in all_events if e.timestamp >= now - timedelta(minutes=5)])

    return {
        "source": source,
        "eventType": eventType,
        "overall": overall,
        "last30Mins": last30,
        "last15Mins": last15,
        "last5Mins": last5
    }
```

### SQLite-Specific Considerations

#### 1. **Thread Safety (check_same_thread)**
```python
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
```

**Why needed?** SQLite by default doesn't allow connections from different threads. FastAPI is multi-threaded, so we disable this check. SQLAlchemy handles thread safety with connection pooling.

**Important:** Only needed for SQLite, not PostgreSQL/MySQL.

#### 2. **JSON Support**
SQLite has built-in JSON support (since version 3.9.0):
```python
outcome = Column(JSON, nullable=True)
```

Works seamlessly with Python dicts! SQLAlchemy handles serialization automatically.

#### 3. **Database File**
```python
"sqlite:///./events.db"  # Creates events.db in current directory
```

The database is a **single file** you can:
- ✅ Copy/backup easily (just copy the file)
- ✅ Delete to reset database (`rm events.db`)
- ✅ View with tools like DB Browser for SQLite
- ⚠️ Usually not committed to git (add to `.gitignore`)

#### 4. **Auto-increment IDs**
SQLite supports auto-increment, but for UUIDs we use:
```python
id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
```

### Seed Script for Initial Data

**seed.py** - Populate database with sample events:
```python
from database import SessionLocal, engine, Base
import models
from datetime import datetime, timedelta
import random
import uuid

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# Clear existing data
db.query(models.Event).delete()
db.commit()

# Generate 1000 sample events
SOURCES = ["access", "incidents", "monitoring", "threat"]
EVENT_TYPES = {
    "access": ["admit", "reject", "door_held"],
    "incidents": ["incident_created", "incident_resolved"],
    "monitoring": ["device_offline", "device_online"],
    "threat": ["detection_alert"]
}

for i in range(1000):
    source = random.choice(SOURCES)
    event_type = random.choice(EVENT_TYPES[source])

    event = models.Event(
        id=str(uuid.uuid4()),
        source=source,
        type=event_type,
        sourceEntity=f"Entity-{i}",
        timestamp=datetime.now() - timedelta(minutes=random.randint(0, 1440)),
        location=random.choice(["SAT", "PHX", "PLX", "TMP", "CHR", "COL"]),
        building=random.choice(["A", "B", "C", "D"]),
        floor=random.choice(["1", "2", "3", "4"]),
        wing=random.choice(["E", "W", "N", "S"]),
        severity=random.choice(["LOW", "MED", "HIGH"])
    )

    db.add(event)

db.commit()
db.close()
print("✅ Created 1000 sample events!")
```

Run with: `python seed.py`

### Advantages: SQLite vs In-Memory

| Feature | In-Memory List | SQLite + SQLAlchemy |
|---------|----------------|---------------------|
| **Persistence** | ❌ Lost on restart | ✅ Saved to disk |
| **Queries** | Manual filtering with Python | ✅ SQL power (joins, aggregates, indexes) |
| **Transactions** | ❌ None | ✅ ACID guarantees |
| **Concurrent access** | ⚠️ Thread-unsafe | ✅ Thread-safe with proper config |
| **Relationships** | ❌ Manual references | ✅ Foreign keys, joins, cascades |
| **Migrations** | ❌ N/A | ✅ Alembic support |
| **Backup** | ❌ Must recreate | ✅ Copy single file |
| **Query optimization** | ❌ Manual | ✅ Indexes, query planning |
| **Data integrity** | ❌ No constraints | ✅ Check constraints, unique, foreign keys |
| **Production ready** | ❌ Demo only | ✅ Yes (for small-medium apps) |

### Database Portability

**The beauty of SQLAlchemy:** Change database by just changing the connection string!

```python
# Development: SQLite
engine = create_engine("sqlite:///./events.db")

# Production: PostgreSQL (same ORM code works!)
engine = create_engine("postgresql://user:pass@localhost/events_db")

# Production: MySQL (same ORM code works!)
engine = create_engine("mysql://user:pass@localhost/events_db")
```

No code changes needed in models, queries, or endpoints! 🎉

### When to Use SQLite vs PostgreSQL

| Use SQLite When | Use PostgreSQL When |
|----------------|---------------------|
| Development/prototyping | Production with high traffic |
| Single-user applications | Multi-user concurrent writes |
| Embedded apps | Distributed systems |
| Testing | Need advanced features (full-text search, JSON querying) |
| Database < 1GB | Database > 1GB or growing rapidly |
| Read-heavy workload | Write-heavy workload |
| Desktop applications | Web applications at scale |

**For this demo app:** SQLite is perfect! ✅

---

## Topic: Background Event Streaming with FastAPI Lifespan

### Requirement: Continuous Event Generation

**Goal:** Create a background process that continuously generates random events and inserts them into the database every 10-100 seconds, but only when `streaming_mode == "on"`.

### Why This Feature?

Makes the dashboard feel "alive" and realistic:
- Events appear automatically without manual creation
- Counters update dynamically as new events arrive
- Perfect for demos and testing
- Simulates real-world event stream

### Implementation Approach: FastAPI Lifespan

**Why NOT use BackgroundTasks?**

`BackgroundTasks` is **request-scoped** - tied to HTTP requests and cleaned up after response. NOT suitable for continuous background processes.

**Correct Approach: Lifespan Context Manager**

Modern FastAPI (2025) uses the **lifespan pattern** for application-wide background tasks:

```python
from contextlib import asynccontextmanager
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: runs when app starts
    print("Starting background worker...")
    task = asyncio.create_task(streaming_worker())

    yield  # Application runs here

    # Shutdown: runs when app stops
    print("Stopping background worker...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Worker stopped")

app = FastAPI(lifespan=lifespan)
```

### Complete Implementation

#### 1. Event Generation Function

Creates a random event and inserts into SQLite database:

```python
async def generate_and_insert_streaming_event():
    """
    Generate a random event and insert into database for streaming mode.
    Creates a new database session for thread safety.
    """
    db = SessionLocal()
    try:
        # Generate random event data
        source = random.choice(SOURCES)
        event_type = random.choice(EVENT_TYPES[source])
        now = datetime.now()

        # Determine processing probabilities
        ingested = random.random() > 0.1  # 90% ingested
        processed = ingested and random.random() > 0.2  # 80% of ingested
        skipped = ingested and not processed and random.random() > 0.5
        has_outcome = processed and random.random() > 0.3  # 70% have outcomes

        # Create event
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
            ingestionTimestamp=(now + timedelta(seconds=random.randint(1, 5))) if ingested else None,
            processedTimestamp=(now + timedelta(seconds=random.randint(10, 60))) if processed else None,
            skippedTimestamp=(now + timedelta(seconds=random.randint(5, 30))) if skipped else None,
            workflowStartTimestamp=(now + timedelta(seconds=random.randint(15, 70))) if has_outcome else None,
            workflowStopTimestamp=(now + timedelta(seconds=random.randint(80, 180))) if has_outcome else None,
            outcome=generate_outcome() if has_outcome else None
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        print(f"[Streaming] Generated event {event.id[:8]}... ({event.source}/{event.type})")
        return event.id

    except Exception as e:
        print(f"[Streaming] Error inserting event: {e}")
        db.rollback()
        return None
    finally:
        db.close()  # Critical: always close session
```

**Key Points:**
- ✅ Creates **new session** for each event (thread-safe)
- ✅ Full error handling with try/except/finally
- ✅ Always closes database session (prevents leaks)
- ✅ Generates realistic data with probabilities

#### 2. Background Worker Loop

Continuous loop that checks streaming mode and generates events:

```python
async def streaming_worker():
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
                    await generate_and_insert_streaming_event()
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
```

**Key Points:**
- ✅ Reads global `streaming_mode` variable (thread-safe - Python GIL ensures atomic reads)
- ✅ Random delay between events (10-100 seconds)
- ✅ Handles `CancelledError` for graceful shutdown
- ✅ Continues even if individual events fail
- ✅ Must **re-raise** `CancelledError` to properly exit

#### 3. Lifespan Context Manager

Manages worker lifecycle with the application:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI.
    Starts background streaming worker on startup, stops it on shutdown.
    """
    # Startup: Create background task
    print("[Streaming] Starting background event streaming...")
    task = asyncio.create_task(streaming_worker())

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


# Create FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)
```

**Key Points:**
- ✅ Uses `@asynccontextmanager` from `contextlib`
- ✅ Creates task with `asyncio.create_task()` (not `run_in_executor`)
- ✅ 5-second timeout for graceful shutdown
- ✅ Proper exception handling for cancellation

### Thread Safety Considerations

#### Global Variable Access

**Reading `streaming_mode`:**
```python
if streaming_mode == "on":
    await generate_and_insert_streaming_event()
```

✅ **SAFE** - Python's GIL (Global Interpreter Lock) ensures atomic reads of simple types like strings.

**Writing to `streaming_mode`:**
```python
@app.put("/api/streaming")
async def toggle_streaming(mode: str):
    global streaming_mode
    streaming_mode = mode  # Simple assignment is atomic
    return {"status": "success"}
```

✅ **SAFE** - Simple string assignment is atomic in Python.

#### Database Session Management

**Critical Pattern:**
```python
db = SessionLocal()  # Create new session
try:
    # ... database operations ...
    db.commit()
except Exception as e:
    db.rollback()
finally:
    db.close()  # ALWAYS close
```

**Why this matters:**
- SQLite allows only **one write** at a time
- Creating fresh session minimizes lock duration
- Always closing prevents connection leaks
- Same pattern used in `process_event_workflow()`

### Testing the Feature

#### 1. Watch Events Being Generated

```bash
# Monitor database growth
watch -n 5 'sqlite3 events.db "SELECT COUNT(*) FROM events;"'

# View latest events
sqlite3 events.db "SELECT id, source, type, timestamp FROM events ORDER BY timestamp DESC LIMIT 5;"
```

#### 2. Toggle Streaming Mode

```bash
# Turn off
curl -X PUT "http://localhost:8000/api/streaming?mode=off"

# Turn on
curl -X PUT "http://localhost:8000/api/streaming?mode=on"
```

#### 3. Observe Server Logs

```
[Streaming] Starting background event streaming...
[Streaming] Background worker started
[Streaming] Generated event a3b4c5d6... (access/admit)
[Streaming] Waiting 47.3 seconds until next event...
[Streaming] Generated event 7e8f9g0h... (threat/detection_alert)
[Streaming] Waiting 82.1 seconds until next event...
^C
[Streaming] Stopping background event streaming...
[Streaming] Received shutdown signal
[Streaming] Worker shutting down gracefully
[Streaming] Worker stopped successfully
```

### Integration with Dashboard

The dashboard's **auto-refresh** (every 10 seconds) automatically displays:
- Increasing event counters
- New events in "Recent Events" table
- Realistic "live" feel without manual intervention

### Comparison: Background Task Approaches

| Approach | Suitable For | Our Use Case |\n|----------|--------------|-------------|\n| **BackgroundTasks** | Request-scoped tasks (email, notifications) | ❌ Wrong choice |\n| **asyncio.create_task()** | Application-wide background loops | ✅ Perfect fit |\n| **threading.Thread** | CPU-bound tasks in thread pool | ❌ Violates asyncio model |\n| **Celery/RQ** | Distributed task queues, production scale | ❌ Overkill for demo |\n| **APScheduler** | Scheduled/cron jobs | ❌ We need continuous loop |\n\n### Why asyncio.create_task() is Perfect

1. ✅ **Runs in same event loop** as FastAPI (no thread conflicts)
2. ✅ **Lifecycle management** via lifespan
3. ✅ **Graceful cancellation** with CancelledError
4. ✅ **No external dependencies** (built into Python)
5. ✅ **Ideal for I/O-bound** background work (database inserts)

### Common Pitfalls and Solutions

#### Pitfall 1: Worker Doesn't Stop on Shutdown

**Symptom:** Server hangs on Ctrl+C

**Cause:** Not re-raising `CancelledError`

**Solution:**
```python
except asyncio.CancelledError:
    print("[Streaming] Cancelled")
    raise  # CRITICAL: must re-raise!
```

#### Pitfall 2: Database Lock Errors

**Symptom:** `sqlite3.OperationalError: database is locked`

**Cause:** Long-lived database sessions

**Solution:** Create fresh session per operation:
```python
db = SessionLocal()  # New session
try:
    # Quick operation
    db.commit()
finally:
    db.close()  # Minimize lock time
```

#### Pitfall 3: Memory Leaks

**Symptom:** Memory usage grows over time

**Cause:** Database sessions not closed

**Solution:** Always use try/finally:
```python
db = SessionLocal()
try:
    # ... operations ...
finally:
    db.close()  # Guaranteed cleanup
```

### Production Enhancements (Future)

For production deployment, consider:

1. **Configurable intervals** - Environment variables instead of hardcoded 10-100s
2. **Rate limiting** - Prevent database overload
3. **Health checks** - Monitor worker status via endpoint
4. **Metrics** - Track event generation rate, errors
5. **PostgreSQL** - Better concurrent write handling than SQLite
6. **Celery/Arq** - Distributed workers for scale
7. **Retry logic** - Exponential backoff for database errors

### Key Takeaways

1. ✅ **Use lifespan** for application-wide background tasks
2. ✅ **asyncio.create_task()** for continuous loops in asyncio apps
3. ✅ **Fresh database sessions** per operation for thread safety
4. ✅ **Always re-raise CancelledError** for graceful shutdown
5. ✅ **Global variable reads are safe** in Python (GIL)
6. ❌ **Never use BackgroundTasks** for non-request tasks

---

## Key Takeaways

1. **For this demo app**: `List[dict]` is perfectly fine for in-memory simulation
2. **For production apps**: Use SQLAlchemy ORM or SQLModel with a real database
3. **Pydantic models**: Great for API validation, not ideal for mutable storage
4. **SQLAlchemy**: THE standard ORM in Python, extremely powerful and mature
5. **SQLModel**: Modern choice that unifies database models and API schemas
6. **Background streaming**: Use FastAPI lifespan + asyncio.create_task() for continuous background processes

---

## Additional Resources

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [FastAPI with Databases Tutorial](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
