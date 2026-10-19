from pathlib import Path
import os
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = Path(os.getenv("OPSHUB_DATA_DIR", str(BASE_DIR / "storage")))
REPORTS_DIR = DATA_DIR / "reports"
MAIL_SINK_DIR = DATA_DIR / "mail_sink"
DB_PATH = Path(os.getenv("OPSHUB_DB_PATH", str(BASE_DIR / "opshub.db")))


class Settings(BaseModel):
    app_name: str = "PulseOps — Enterprise Operations & Reliability Command Center"
    version: str = "2.4.0"
    base_dir: Path = BASE_DIR
    data_dir: Path = DATA_DIR
    reports_dir: Path = REPORTS_DIR
    mail_sink_dir: Path = MAIL_SINK_DIR
    db_path: Path = DB_PATH
    jwt_secret: str = os.getenv("OPSHUB_JWT_SECRET", "opshub-super-secret-argon-token-key-2026")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440


settings = Settings()
