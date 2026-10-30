import json
import logging
import os
import sqlite3
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data.db")

logging.basicConfig(
    filename=os.path.join(BASE, "app.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("app")

app = Flask(__name__, static_folder="static")


# ---------- Database ----------

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, date TEXT, people TEXT, agenda TEXT,
            notes TEXT, decisions TEXT, links TEXT
        );
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER, task TEXT NOT NULL, owner TEXT NOT NULL,
            due TEXT, status TEXT DEFAULT 'open', outcome TEXT, history TEXT
        );
        CREATE TABLE IF NOT EXISTS docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, text TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT, level TEXT, message TEXT
        );
    """)
    conn.commit()
    conn.close()


def query(sql, args=()):
    conn = db()
    rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    conn.close()
    return rows


def execute(sql, args=()):
    conn = db()
    cur = conn.execute(sql, args)
    conn.commit()
    conn.close()
    return cur.lastrowid


def event(level, message):
    if level == "WARN":
        log.warning(message)
    else:
        log.info(message)
    execute("INSERT INTO events (time, level, message) VALUES (?, ?, ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), level, message))


def get_meeting(meeting_id):
    rows = query("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    if not rows:
        return None
    m = rows[0]
    m["decisions"] = json.loads(m["decisions"] or "[]")
    m["links"] = json.loads(m["links"]) if m["links"] else None
    return m


def get_action(action_id):
    rows = query("SELECT * FROM actions WHERE id = ?", (action_id,))
    if not rows:
        return None
    a = rows[0]
    a["history"] = json.loads(a["history"] or "[]")
    return a


def bad(message, code=400):
    event("WARN", message)
    return jsonify({"error": message}), code


def field(data, name):
    return str(data.get(name) or "").strip()


# ---------- Pages ----------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/data")
def all_data():
    meetings = [get_meeting(r["id"]) for r in query("SELECT id FROM meetings ORDER BY id")]
    actions = [get_action(r["id"]) for r in query("SELECT id FROM actions ORDER BY id")]
    docs = query("SELECT * FROM docs ORDER BY id")
    events = query("SELECT * FROM events ORDER BY id DESC LIMIT 30")
    return jsonify({"meetings": meetings, "actions": actions, "docs": docs, "events": events})


# ---------- Meetings ----------

@app.route("/api/meetings", methods=["POST"])
def add_meeting():
    data = request.get_json(silent=True) or {}
    title = field(data, "title")
    if not title:
        return bad("Please enter a meeting title")
    decisions = [d.strip() for d in field(data, "decisions").split("\n") if d.strip()]
    meeting_id = execute(
        "INSERT INTO meetings (title, date, people, agenda, notes, decisions) VALUES (?, ?, ?, ?, ?, ?)",
        (title, field(data, "date"), field(data, "people"), field(data, "agenda"),
         field(data, "notes"), json.dumps(decisions)))
    event("INFO", "Meeting created: " + title)
    return jsonify(get_meeting(meeting_id)), 201


@app.route("/api/meetings/<int:meeting_id>", methods=["DELETE"])
def delete_meeting(meeting_id):
    m = get_meeting(meeting_id)
    if not m:
        return bad("Meeting not found", 404)
    execute("DELETE FROM actions WHERE meeting_id = ?", (meeting_id,))
    execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    event("INFO", "Meeting deleted: " + m["title"])
    return jsonify({"ok": True})


@app.route("/api/meetings/<int:meeting_id>/link", methods=["POST"])
def link_docs(meeting_id):
    m = get_meeting(meeting_id)
    if not m:
        return bad("Meeting not found", 404)
    text = (m["title"] + " " + m["agenda"] + " " + m["notes"]).lower()
    words = set(w for w in "".join(c if c.isalnum() else " " for c in text).split() if len(w) > 4)
    found = []
    for d in query("SELECT * FROM docs"):
        doc_text = (d["title"] + " " + d["text"]).lower()
        if any(w in doc_text for w in words):
            found.append(d["title"])
    execute("UPDATE meetings SET links = ? WHERE id = ?", (json.dumps(found), meeting_id))
    event("INFO", "Linked %d document(s) to meeting: %s" % (len(found), m["title"]))
    return jsonify({"links": found})


@app.route("/api/meetings/<int:meeting_id>/brief")
def brief(meeting_id):
    m = get_meeting(meeting_id)
    if not m:
        return bad("Meeting not found", 404)
    open_items = query("SELECT task, owner, due FROM actions WHERE meeting_id = ? AND status = 'open'",
                       (meeting_id,))
    summary = m["notes"].split(".")[0] + "." if m["notes"] else "No notes"
    event("INFO", "Brief generated for meeting: " + m["title"])
    return jsonify({
        "title": m["title"],
        "date": m["date"],
        "people": m["people"],
        "summary": summary,
        "decisions": m["decisions"],
        "open_items": open_items,
    })


@app.route("/api/carry-forward", methods=["POST"])
def carry_forward():
    data = request.get_json(silent=True) or {}
    source = get_meeting(data.get("from"))
    target = get_meeting(data.get("to"))
    if not source or not target:
        return bad("Pick two meetings")
    if source["id"] == target["id"]:
        return bad("Pick two different meetings")
    rows = query("SELECT id FROM actions WHERE meeting_id = ? AND status = 'open'", (source["id"],))
    for r in rows:
        a = get_action(r["id"])
        a["history"].append("Carried forward to " + target["title"])
        execute("UPDATE actions SET meeting_id = ?, history = ? WHERE id = ?",
                (target["id"], json.dumps(a["history"]), a["id"]))
    event("INFO", "Carried forward %d open item(s) to %s" % (len(rows), target["title"]))
    return jsonify({"moved": len(rows)})


# ---------- Action items ----------

@app.route("/api/actions", methods=["POST"])
def add_action():
    data = request.get_json(silent=True) or {}
    m = get_meeting(data.get("meeting_id"))
    if not m:
        return bad("Add a meeting first")
    task = field(data, "task")
    owner = field(data, "owner")
    if not task:
        return bad("Please enter a task")
    if not owner:
        return bad("Please enter an owner")
    history = ["Created in " + m["title"]]
    action_id = execute(
        "INSERT INTO actions (meeting_id, task, owner, due, history) VALUES (?, ?, ?, ?, ?)",
        (m["id"], task, owner, field(data, "due"), json.dumps(history)))
    event("INFO", "Action item created: %s (owner %s)" % (task, owner))
    return jsonify(get_action(action_id)), 201


@app.route("/api/actions/<int:action_id>/close", methods=["POST"])
def close_action(action_id):
    a = get_action(action_id)
    if not a:
        return bad("Action item not found", 404)
    if a["status"] == "closed":
        return bad("Action item is already closed")
    outcome = field(request.get_json(silent=True) or {}, "outcome") or "No outcome given"
    a["history"].append("Closed: " + outcome)
    execute("UPDATE actions SET status = 'closed', outcome = ?, history = ? WHERE id = ?",
            (outcome, json.dumps(a["history"]), action_id))
    event("INFO", "Action item closed: " + a["task"])
    return jsonify(get_action(action_id))


@app.route("/api/actions/<int:action_id>/reassign", methods=["POST"])
def reassign(action_id):
    a = get_action(action_id)
    if not a:
        return bad("Action item not found", 404)
    owner = field(request.get_json(silent=True) or {}, "owner")
    if not owner:
        return bad("Please enter a new owner")
    a["history"].append("Reassigned from %s to %s" % (a["owner"], owner))
    execute("UPDATE actions SET owner = ?, history = ? WHERE id = ?",
            (owner, json.dumps(a["history"]), action_id))
    event("INFO", "Action item reassigned: %s -> %s" % (a["task"], owner))
    return jsonify(get_action(action_id))


# ---------- Knowledge base ----------

@app.route("/api/docs", methods=["POST"])
def add_doc():
    data = request.get_json(silent=True) or {}
    title = field(data, "title")
    if not title:
        return bad("Please enter a document title")
    doc_id = execute("INSERT INTO docs (title, text) VALUES (?, ?)", (title, field(data, "text")))
    event("INFO", "Document added: " + title)
    return jsonify({"id": doc_id, "title": title}), 201


# ---------- Errors ----------

@app.errorhandler(Exception)
def handle_error(e):
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    log.exception("Unexpected error on %s %s", request.method, request.path)
    return jsonify({"error": "Something went wrong"}), 500


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
