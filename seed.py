"""
Seed script to populate the database with sample events.
Run this script to create initial data for development/testing.

Usage:
    python seed.py
"""

from database import SessionLocal, engine, Base
import models
from datetime import datetime, timedelta
import random
import uuid

# Event type definitions
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


def seed_database(count=1000):
    """Generate and insert sample events into the database"""
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Create database session
    db = SessionLocal()

    try:
        # Clear existing data
        print("Clearing existing events...")
        db.query(models.Event).delete()
        db.commit()

        # Generate sample events
        print(f"Generating {count} sample events...")
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

            event = models.Event(
                id=str(uuid.uuid4()),
                source=source,
                type=event_type,
                sourceEntity=random.choice(SOURCE_ENTITIES[source]),
                timestamp=timestamp,
                location=random.choice(LOCATIONS),
                building=random.choice(BUILDINGS),
                floor=random.choice(FLOORS),
                wing=random.choice(WINGS),
                severity=random.choice(SEVERITIES),
                ingestionTimestamp=(timestamp + timedelta(seconds=random.randint(1, 5))) if ingested else None,
                processedTimestamp=(timestamp + timedelta(seconds=random.randint(10, 60))) if processed else None,
                skippedTimestamp=(timestamp + timedelta(seconds=random.randint(5, 30))) if skipped else None,
                workflowStartTimestamp=(timestamp + timedelta(seconds=random.randint(15, 70))) if has_outcome else None,
                workflowStopTimestamp=(timestamp + timedelta(seconds=random.randint(80, 180))) if has_outcome else None,
                outcome=generate_outcome() if has_outcome else None
            )

            db.add(event)

            # Commit in batches for better performance
            if (i + 1) % 100 == 0:
                db.commit()
                print(f"  Created {i + 1}/{count} events...")

        # Final commit
        db.commit()
        print(f"✅ Successfully created {count} sample events!")

        # Print statistics
        total_events = db.query(models.Event).count()
        ingested_count = db.query(models.Event).filter(models.Event.ingestionTimestamp.isnot(None)).count()
        processed_count = db.query(models.Event).filter(models.Event.processedTimestamp.isnot(None)).count()

        print(f"\nDatabase Statistics:")
        print(f"  Total events: {total_events}")
        print(f"  Ingested: {ingested_count}")
        print(f"  Processed: {processed_count}")
        print(f"  With outcomes: {db.query(models.Event).filter(models.Event.outcome.isnot(None)).count()}")

    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Security Events Database Seeder")
    print("=" * 60)
    seed_database(1000)
    print("\nDatabase seeding complete! You can now start the application.")
    print("=" * 60)
