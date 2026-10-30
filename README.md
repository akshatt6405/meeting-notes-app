meeting notes app
this is a app for meetings and action items.

to run
pip install -r requirements.txt
python app.py
then open localhost:5000

made with python flask and sqlite database, frontend is html and javascript (static/index.html)
data saved in data.db file it makes it automatically

features - add meetings with title date participants agenda notes decisions, delete meeting, action items with owner and due date, close item with outcome, reassign item, history of item, overdue shown in red, carry forward open items to other meeting, catch up brief for people who missed meeting, knowledge base add documents and link docs to meeting (keyword match), activity log on page, validation for empty fields
API - GET /api/data, POST /api/meetings, DELETE /api/meetings/id, POST /api/meetings/id/link, GET /api/meetings/id/brief, POST /api/actions, POST /api/actions/id/close, POST /api/actions/id/reassign, POST /api/carry-forward, POST /api/docs
logging is in app.log file using python logging (INFO WARNING ERROR)
deploy on render, start command gunicorn app:app

AI - not done, summary is just first line of notes
no login
data can reset on free hosting
