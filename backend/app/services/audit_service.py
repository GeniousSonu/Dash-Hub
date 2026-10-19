import json
import sqlite3
from typing import Any

from backend.app.core.database import new_uuid, utc_now_iso


class AuditService:
    @staticmethod
    def log_event(
        conn: sqlite3.Connection,
        *,
        actor_user_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        summary: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
    ) -> str:
        event_id = new_uuid()
        conn.execute(
            """
            INSERT INTO activity_events (
                id, actor_user_id, entity_type, entity_id, action, summary, before_json, after_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                actor_user_id,
                entity_type,
                entity_id,
                action,
                summary,
                json.dumps(before_state or {}, default=str),
                json.dumps(after_state or {}, default=str),
                utc_now_iso(),
            ),
        )
        return event_id

    @staticmethod
    def list_events(
        conn: sqlite3.Connection,
        entity_type: str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT e.*, u.full_name AS actor_name, u.role AS actor_role
            FROM activity_events e
            LEFT JOIN users u ON e.actor_user_id = u.id
            WHERE 1=1
        """
        params: list[Any] = []
        if entity_type:
            query += " AND e.entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND e.entity_id = ?"
            params.append(entity_id)
        query += " ORDER BY e.created_at DESC, e.rowid DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
