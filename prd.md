I would like to build an dashboard for security systems events platform. In a nutshell, the security system basically ingests events from various security systems (sources), stores in a database and, depending on the event type, runs the event via an agentic workflow that produes possible outcomes: immediate actions, short-term actions, long-term actions or notifications. 

But this app is only concerned with the dashboard aspect of the security application.

## Types

Here are the types in the system and their possible values:

- **source**: the following values are possible values: 
    - *access*
    - *incidents*
    - *monitoring*
    - *threat*
- **eventType**: the source determines the possible event types:
    - *access*: admit|reject|door_held
    - *incidents*: incident_created|incident_resolved
    - *monitoring*: device_offline|devic_online
    - *threat*: detection_alert  
- **sourceEntity**: the source determins tge source entity:
    - *access*: door name
    - *incidents*: incident number
    - *monitoring*: device name
    - *threat*: camera name  

## Backend

An API backend that supports the following API Endpoints:

- GET /api/events?type={source}&type={event_type}&ingested={true/false}&processed={true/false}&skipped={true/false}&outcome={true/false}

This endpoint queries the events database using the requested parameters and returns a JSON payload:

```json
{
    "source": "All + Possible values are values as above",
    "streamingMode": "on",
    "eventType": "All + Possible values are values as above",
    "overall": 18990,
    "last30Mins": 1956,
    "last15Mins": 765,
    "last5Mins": 432
}
```

- PUT /api/streaming?mode={on/off}

This API Endpoint toggles the streaming mode on or off and returns success (status 201) without a payload.

- POST /api/query?prompt={query to search the events database using a natural language}

This endpoint submits the natural language query prompt to an agent which returns an array of events that match the query:
```json
[
    {
        "id": "guid",
        "source": "please refer to source type above",
        "type": "please refer to event type above",
        "sourceEntity": "please refer to source entity above",
        "timestamp": "non-nullable occurrence time",
        "location": "SAT|PHX|PLX|TMP|CHR|COL",
        "building": "A|B|C|D",
        "floor": "1|2|3|4",
        "wing": "E|W|N|S",
        "severity": "LOW|MED|HIGH",
        "ingestionTimestamp": "nullable ingestion time",
        "processedTimestamp": "nullable processed time",
        "skippedTimestamp": "nullable skipped time",
        "workflowStartTimestamp": "nullable workflow start time",
        "workflowStopTimestamp": "nullable workflow stop time",
        "outcome": {
            "immediate": [
                {
                    "title": "",
                    "desc": "",
                    "triggerAccess": true|false,
                    "triggerIncidents": true|false,
                    "notifySecurity": true|false
                }
            ],
            "shortTerm": [
                {
                    "title": "",
                    "desc": "",
                    "triggerAccess": true|false,
                    "triggerIncidents": true|false,
                    "notifySecurity": true|false
                }
            ],
            "longTerm": [
                {
                    "title": "",
                    "desc": "",
                    "triggerAccess": true|false,
                    "triggerIncidents": true|false,
                    "notifySecurity": true|false
                }
            ]
        }
    }
]
```

- POST /api/events?mode={sync|async}

This endpoint submits an event to the backend to process. The mode decides on whether to process the event synchornously or asynchornouly. The event payload: 

```json
{
    "id": "guid",
    "source": "please refer to source type above",
    "type": "please refer to event type above",
    "sourceEntity": "please refer to source entity above",
    "timestamp": "non-nullable occurrence time",
    "location": "SAT|PHX|PLX|TMP|CHR|COL",
    "building": "A|B|C|D",
    "floor": "1|2|3|4",
    "wing": "E|W|N|S",
    "severity": "LOW|MED|HIGH"
}
```

## Front End

A single Page dashboard application that shows the following Elements:
- **Streaming Status**: Either on or off. Right next to it, allow the user to toggle it.
- **Filter Group**: This contains:
    - Dropdown to select the source. make `All` the default.
    - checkbox: Ingested
    - Checkbox: Processed
    - Checkbox: Skipped
    - Checkbox: Outcome
    - Dropdown to select the event type. make `All` the default.
    - The seach should be invoked when the user changes any of the filter parameters. In other words, there is no button to start the filter.
- **Counters**: 
    - 4 cards to show counters for `Overall`, `Last 30 Mins`, `Last 15 Mins`, `Last 5 Mins`.
    - A button to create a manual event. This should pop up a form to allow users to enter a manual event requesting the elements shown above.
- **Query**: 
    - A text box to allow users to enter a natural language prompt. Please add a place holder to guide users what to do.
    - Results table to show th events that match query.

## Technology:

### Backend

I want two implementations: one in Python (FastAPI) and one in Golang. Both use HTMX to do server-side rendering...no React please.  

**Given that we don't have a database, pleae randomize values to simulate work.** 

### Frontend

Please use HTMX with minimal JavaScript. Use a simplistic styling as well. But please create a periodic timer that fires every 5 seconds to update the counter from the backend.  


