# -*- coding: utf-8 -*-
"""FastAPI web front-end for the Azaran Teb clinic accounting app.

Reuses the desktop app's data layer (app.models, app.settings, app.date_utils,
app.money_utils) so both the Qt5 GUI and this web UI share one SQLite database.
"""