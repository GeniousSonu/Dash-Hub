import os
import sys

from desktop.services.api_client import OpsHubDesktopClient

try:
    from PySide6.QtWidgets import QApplication
    from desktop.ui.main_window import OpsHubMainWindow, PYSIDE6_AVAILABLE
except ImportError:
    PYSIDE6_AVAILABLE = False


def main() -> int:
    if "--server" in sys.argv:
        import uvicorn
        from backend.app.main import app
        uvicorn.run(app, host="127.0.0.1", port=8000)
        return 0

    api_url = os.getenv("OPSHUB_API_URL")
    client = OpsHubDesktopClient(base_url=api_url)

    if not PYSIDE6_AVAILABLE:
        summary = client.get_dashboard_summary()
        print("OpsHub Backend Engine initialized. Live KPIs:", summary["kpis"])
        print("Install PySide6 in your virtual environment to launch desktop GUI.")
        return 0

    qt_app = QApplication(sys.argv)
    win = OpsHubMainWindow(client)
    win.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
