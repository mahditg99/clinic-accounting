# -*- coding: utf-8 -*-
"""Entry point for Azaran Teb Clinic Accounting."""
from __future__ import annotations

import sys

from app.database import init_db
from app.utils import Qt, apply_app_font, best_persian_font, load_app_fonts, \
    setup_scaling


def main():
    # type: () -> int
    # Uniform fractional display scaling (QT_SCALE_FACTOR / QT_FONT_DPI)
    # must be configured BEFORE the QApplication instance is created.
    setup_scaling()

    # Initialize the SQLite database (creates schema + seed on first run).
    init_db()

    app = Qt.QtWidgets.QApplication.instance() or Qt.QtWidgets.QApplication(sys.argv)
    app.setLayoutDirection(Qt.QtCore.Qt.RightToLeft)
    load_app_fonts()
    apply_app_font(size=10)

    # Force the cross-platform Fusion style so the global QSS paints
    # consistently (the native Windows theme would override many rules).
    try:
        app.setStyle("Fusion")
    except Exception:
        pass

    # Global QSS theme (buttons, tables, cards, sidebar, scrollbars…).
    from app.theme import apply_theme
    apply_theme(app)

    # Hardware license gate. Only bites in the packaged exe (or when
    # AZARAN_LICENSE_ENFORCE=1); shows the activation dialog otherwise.
    from app import license as license_mod
    if not license_mod.enforce_startup():
        return 0

    # v2 desktop UI (mirrors the web app): login dialog + sidebar shell.
    from app.ui.shell import run_desktop
    window = run_desktop()
    if window is None:
        return 0
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
