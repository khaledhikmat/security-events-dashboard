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

## Key Takeaways

1. **For this demo app**: `List[dict]` is perfectly fine for in-memory simulation
2. **For production apps**: Use SQLAlchemy ORM or SQLModel with a real database
3. **Pydantic models**: Great for API validation, not ideal for mutable storage
4. **SQLAlchemy**: THE standard ORM in Python, extremely powerful and mature
5. **SQLModel**: Modern choice that unifies database models and API schemas

---

## Additional Resources

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [FastAPI with Databases Tutorial](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
