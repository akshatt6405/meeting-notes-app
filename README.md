# Meeting Notes

A small web app for writing down meetings, tracking action items until they are closed, and giving a catch-up brief to anyone who missed a meeting.

## How to run

    pip install -r requirements.txt
    python app.py

Open http://localhost:5000

## Tech stack
- **Backend:** Python + Flask
- **Database:** SQLite (`data.db`, created automatically on first run)
- **Frontend:** one HTML page with plain JavaScript (`static/index.html`) that calls the API

## Features
- **Meetings:** title, date, participants, agenda, notes and decisions. Meetings can be deleted.
- **Action items:** task, owner and due date, linked to a meeting. Close an item with an outcome, or reassign it. Overdue items are marked.
- **History:** every action item keeps a history (created, reassigned, carried forward, closed).
- **Carry forward:** move all open items from one meeting to another.
- **Catch-up brief:** for one meeting, shows who was there, a one-line summary, the decisions and the open items.
- **Knowledge base:** add documents. "Link docs" on a meeting finds documents that share keywords with it.
- **Activity log:** key events shown on the page.
- **Validation:** the server checks required fields and returns a clear error message, which the page shows.

## API

| Method | URL | What it does |
|---|---|---|
| GET | `/api/data` | All meetings, action items, documents and the latest events |
| POST | `/api/meetings` | Create a meeting |
| DELETE | `/api/meetings/<id>` | Delete a meeting and its action items |
| POST | `/api/meetings/<id>/link` | Link knowledge base documents to a meeting |
| GET | `/api/meetings/<id>/brief` | Catch-up brief for a meeting |
| POST | `/api/actions` | Create an action item |
| POST | `/api/actions/<id>/close` | Close an action item with an outcome |
| POST | `/api/actions/<id>/reassign` | Change the owner |
| POST | `/api/carry-forward` | Move open items from one meeting to another |
| POST | `/api/docs` | Add a knowledge base document |

## Database
Four tables: `meetings`, `actions`, `docs` and `events`. Decisions, links and action history are stored as JSON text.

## Logging
Python `logging` writes to `app.log` with a timestamp and level (INFO / WARNING / ERROR). It logs key events (meeting created, item closed, item reassigned, carried forward), validation errors, and unexpected errors with the stack trace. Key events are also saved in the `events` table and shown on the page.

## Deploy (Render)
1. Push this folder to a GitHub repo.
2. On render.com, create a new Web Service from the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`

## Assumptions
- One team uses the app, so there are no users or login.
- Meetings are entered by hand.

## Known limitations
- No AI. The summary and brief use simple rules (the first sentence of the notes), and document linking is keyword matching.
- No login or security.
- SQLite on a free host can be reset when the app restarts or redeploys.
- No request ID in the logs.
