"""
Minimal Flask app for database migration commands.

`app.py` loads the evaluator models (DeBERTa, SBERT, ...) at import time,
which is slow and pointless for schema work, so migrations use this app,
which only has the database attached. Run from `main_cap/cap`:

    flask --app db_manage db migrate -m "describe the change"   # after editing models.py
    flask --app db_manage db upgrade                            # apply (app.py also does this on startup)
"""

from flask import Flask

from account_routes import init_accounts

app = Flask(__name__)
init_accounts(app, auto_upgrade=False)
