"""Memory Agent.

SQLite-backed persistent session memory.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph.state import PipelineState, CheckpointRecord, Message


class MemoryAgent:
    def __init__(self, memory_dir: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_memory_dir = Path(base) / "memory"
        self.memory_dir = str(Path(memory_dir) if memory_dir else self._resolve_memory_dir(project_memory_dir))
        self.db_path = os.path.join(self.memory_dir, "memory.sqlite3")
        self._copy_existing_db(project_memory_dir / "memory.sqlite3")
        self._ensure_db_file_writable()
        self._init_db()

    def _resolve_memory_dir(self, project_memory_dir: Path) -> Path:
        candidates = []
        project_root = project_memory_dir.parent
        runtime_root = os.getenv("STRUCTPILOT_RUNTIME_DIR")
        if runtime_root:
            candidates.append(Path(runtime_root) / "memory")
        candidates.extend(
            [
                project_root / "runtime" / "memory",
                Path.home() / "Documents" / "struct" / "StructPilot_v4_runtime" / "memory",
                Path(tempfile.gettempdir()) / "StructPilot_v4" / "memory",
                project_memory_dir,
            ]
        )
        tried = []
        for path in candidates:
            try:
                path.mkdir(parents=True, exist_ok=True)
                probe = path / ".write_test"
                probe.write_text("", encoding="utf-8")
                probe.unlink(missing_ok=True)
                return path
            except OSError as exc:
                tried.append(f"{path} ({exc})")
        raise PermissionError("无法创建可写数据库目录：" + " | ".join(tried))

    def _copy_existing_db(self, source_db: Path) -> None:
        target_db = Path(self.memory_dir) / "memory.sqlite3"
        if target_db.exists() or not source_db.exists() or source_db == target_db:
            return
        try:
            shutil.copy2(source_db, target_db)
            target_db.chmod(stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass

    def _ensure_db_file_writable(self) -> None:
        db = Path(self.db_path)
        if not db.exists():
            return
        try:
            db.chmod(stat.S_IREAD | stat.S_IWRITE)
        except OSError:
            pass

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    session_name TEXT,
                    created_at TEXT,
                    last_updated TEXT,
                    software TEXT,
                    current_cp_id TEXT,
                    current_cp_name TEXT,
                    session_started INTEGER,
                    completed_json TEXT,
                    failed_json TEXT,
                    skipped_json TEXT,
                    params_json TEXT,
                    last_qc_result_json TEXT,
                    requires_human_approval INTEGER,
                    in_fault_mode INTEGER,
                    error TEXT,
                    error_node TEXT
                )
                """
            )
            existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
            if "session_name" not in existing_cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN session_name TEXT")
            if "session_summary" not in existing_cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN session_summary TEXT")
            # Add index for sessions table (used for sorting by last_updated)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_updated ON sessions(last_updated)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    action_tag TEXT,
                    metadata_json TEXT
                )
                """
            )
            # Add indexes for messages table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS message_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    message_id INTEGER,
                    image_name TEXT,
                    image_path TEXT,
                    mime_type TEXT,
                    sha256 TEXT,
                    width INTEGER,
                    height INTEGER,
                    caption TEXT,
                    source_type TEXT,
                    created_at TEXT
                )
                """
            )
            # Add indexes for message_images table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_message_images_session_id ON message_images(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_message_images_message_id ON message_images(message_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_records (
                    session_id TEXT,
                    cp_id TEXT,
                    cp_name_cn TEXT,
                    status TEXT,
                    entered_at TEXT,
                    completed_at TEXT,
                    user_feedback TEXT,
                    qc_summary TEXT,
                    qc_passed INTEGER,
                    params_captured_json TEXT,
                    notes TEXT,
                    PRIMARY KEY (session_id, cp_id)
                )
                """
            )
            # Add indexes for checkpoint_records table
            conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoint_records_session_id ON checkpoint_records(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoint_records_status ON checkpoint_records(status)")

    def ingest_user_message(self, state: PipelineState, user_text: str) -> None:
        state.user_input = user_text
        state.user_input_lower = user_text.lower().strip()
        if not state.session_id:
            state.session_id = "default_session"

    def add_pending_image(self, state: PipelineState, image_ref: Dict[str, Any]) -> None:
        state.pending_images.append(image_ref)
        state.touch()

    def _dump(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _get_session_name(self, state: PipelineState) -> str:
        return getattr(state, "session_name", "") or state.session_id

    def _serialize_state(self, state: PipelineState) -> Dict[str, Any]:
        return {
            "session_id": state.session_id,
            "session_name": self._get_session_name(state),
            "created_at": state.created_at,
            "last_updated": state.last_updated,
            "software": state.software,
            "current_cp_id": state.current_cp_id,
            "current_cp_name": state.current_cp_name,
            "session_started": int(state.session_started),
            "completed_json": self._dump(state.completed),
            "failed_json": self._dump(state.failed),
            "skipped_json": self._dump(state.skipped),
            "params_json": self._dump(state.params),
            "last_qc_result_json": self._dump(state.last_qc_result),
            "session_summary": getattr(state, "session_summary", ""),
            "requires_human_approval": int(state.requires_human_approval),
            "in_fault_mode": int(state.in_fault_mode),
            "error": state.error,
            "error_node": state.error_node,
        }

    def save_state(self, state: PipelineState) -> Dict[str, Any]:
        snapshot = self._serialize_state(state)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, session_name, created_at, last_updated, software, current_cp_id,
                    current_cp_name, session_started, completed_json, failed_json,
                    skipped_json, params_json, last_qc_result_json,
                    session_summary, requires_human_approval, in_fault_mode, error, error_node
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    session_name=excluded.session_name,
                    created_at=excluded.created_at,
                    last_updated=excluded.last_updated,
                    software=excluded.software,
                    current_cp_id=excluded.current_cp_id,
                    current_cp_name=excluded.current_cp_name,
                    session_started=excluded.session_started,
                    completed_json=excluded.completed_json,
                    failed_json=excluded.failed_json,
                    skipped_json=excluded.skipped_json,
                    params_json=excluded.params_json,
                    last_qc_result_json=excluded.last_qc_result_json,
                    session_summary=excluded.session_summary,
                    requires_human_approval=excluded.requires_human_approval,
                    in_fault_mode=excluded.in_fault_mode,
                    error=excluded.error,
                    error_node=excluded.error_node
                """,
                (
                    snapshot["session_id"], snapshot["session_name"], snapshot["created_at"], snapshot["last_updated"],
                    snapshot["software"], snapshot["current_cp_id"], snapshot["current_cp_name"],
                    snapshot["session_started"], snapshot["completed_json"], snapshot["failed_json"],
                    snapshot["skipped_json"], snapshot["params_json"], snapshot["last_qc_result_json"],
                    snapshot["session_summary"], snapshot["requires_human_approval"], snapshot["in_fault_mode"],
                    snapshot["error"], snapshot["error_node"],
                ),
            )
            conn.execute("DELETE FROM messages WHERE session_id=?", (state.session_id,))
            conn.execute("DELETE FROM message_images WHERE session_id=?", (state.session_id,))
            for m in state.messages:
                cursor = conn.execute(
                    """
                    INSERT INTO messages (session_id, role, content, timestamp, action_tag, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (state.session_id, m.role, m.content, m.timestamp, m.action_tag, self._dump(m.metadata)),
                )
                message_id = cursor.lastrowid
                for img in getattr(m, "image_refs", []) or []:
                    conn.execute(
                        """
                        INSERT INTO message_images (
                            session_id, message_id, image_name, image_path, mime_type, sha256,
                            width, height, caption, source_type, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            state.session_id,
                            message_id,
                            img.get("image_name", ""),
                            img.get("image_path", ""),
                            img.get("mime_type", ""),
                            img.get("sha256", ""),
                            img.get("width"),
                            img.get("height"),
                            img.get("caption", ""),
                            img.get("source_type", "upload"),
                            img.get("created_at", datetime.now().isoformat()),
                        ),
                    )
            conn.execute("DELETE FROM checkpoint_records WHERE session_id=?", (state.session_id,))
            for rec in state.checkpoint_records.values():
                conn.execute(
                    """
                    INSERT INTO checkpoint_records (
                        session_id, cp_id, cp_name_cn, status, entered_at, completed_at,
                        user_feedback, qc_summary, qc_passed, params_captured_json, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        state.session_id, rec.cp_id, rec.cp_name_cn, rec.status, rec.entered_at,
                        rec.completed_at, rec.user_feedback, rec.qc_summary, int(rec.qc_passed),
                        self._dump(rec.params_captured), rec.notes,
                    ),
                )
        return snapshot

    def capture_state(self, state: PipelineState) -> Dict[str, Any]:
        return self.save_state(state)

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, session_name, last_updated, current_cp_id, current_cp_name FROM sessions ORDER BY last_updated DESC"
            ).fetchall()
        return [
            {
                "session_id": r[0],
                "session_name": r[1] or r[0],
                "last_updated": r[2],
                "current_cp_id": r[3],
                "current_cp_name": r[4],
            }
            for r in rows
        ]

    def rename_session(self, session_id: str, session_name: str) -> None:
        clean_name = session_name.strip() or session_id
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET session_name=?, last_updated=? WHERE session_id=?",
                (clean_name, datetime.now().isoformat(), session_id),
            )

    def delete_session(self, session_id: str) -> None:
        """Permanently remove a session and all of its messages/images/checkpoints."""
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM message_images WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM checkpoint_records WHERE session_id=?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))

    def get_latest_session_id(self) -> Optional[str]:
        sessions = self.list_sessions()
        return sessions[0]["session_id"] if sessions else None

    def load_state(self, session_id: str) -> Optional[PipelineState]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if not row:
                return None
            cols = [d[0] for d in conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).description]
            data = dict(zip(cols, row))
            msg_rows = conn.execute(
                "SELECT id, role, content, timestamp, action_tag, metadata_json FROM messages WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            image_rows = conn.execute(
                """
                SELECT message_id, image_name, image_path, mime_type, sha256,
                       width, height, caption, source_type, created_at
                FROM message_images WHERE session_id=? ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()
            rec_rows = conn.execute(
                "SELECT * FROM checkpoint_records WHERE session_id=?",
                (session_id,),
            ).fetchall()
            rec_cols = [d[0] for d in conn.execute("SELECT * FROM checkpoint_records WHERE session_id=?", (session_id,)).description]

        state = PipelineState(
            session_id=data.get("session_id", session_id),
            created_at=data.get("created_at", ""),
            last_updated=data.get("last_updated", ""),
            software=data.get("software", "relion"),
            current_cp_id=data.get("current_cp_id", "cp_01"),
            current_cp_name=data.get("current_cp_name", ""),
            session_started=bool(data.get("session_started", 0)),
            completed=json.loads(data.get("completed_json", "[]")),
            failed=json.loads(data.get("failed_json", "[]")),
            skipped=json.loads(data.get("skipped_json", "[]")),
            params=json.loads(data.get("params_json", "{}")),
            last_qc_result=json.loads(data.get("last_qc_result_json", "{}")),
            session_summary=data.get("session_summary") or "",
            requires_human_approval=bool(data.get("requires_human_approval", 0)),
            in_fault_mode=bool(data.get("in_fault_mode", 0)),
            error=data.get("error"),
            error_node=data.get("error_node"),
        )
        setattr(state, "session_name", data.get("session_name") or state.session_id)
        images_by_message: Dict[int, List[Dict[str, Any]]] = {}
        for image_row in image_rows:
            message_id = int(image_row[0])
            images_by_message.setdefault(message_id, []).append({
                "image_name": image_row[1],
                "image_path": image_row[2],
                "mime_type": image_row[3],
                "sha256": image_row[4],
                "width": image_row[5],
                "height": image_row[6],
                "caption": image_row[7],
                "source_type": image_row[8],
                "created_at": image_row[9],
            })
        for message_id, role, content, timestamp, action_tag, metadata_json in msg_rows:
            state.messages.append(Message(
                role=role,
                content=content,
                timestamp=timestamp,
                action_tag=action_tag,
                metadata=json.loads(metadata_json or "{}"),
                image_refs=images_by_message.get(int(message_id), []),
            ))
        for rec in rec_rows:
            rec_data = dict(zip(rec_cols, rec))
            state.checkpoint_records[rec_data["cp_id"]] = CheckpointRecord(
                cp_id=rec_data["cp_id"],
                cp_name_cn=rec_data.get("cp_name_cn", ""),
                status=rec_data.get("status", "pending"),
                entered_at=rec_data.get("entered_at"),
                completed_at=rec_data.get("completed_at"),
                user_feedback=rec_data.get("user_feedback", ""),
                qc_summary=rec_data.get("qc_summary", ""),
                qc_passed=bool(rec_data.get("qc_passed", 0)),
                params_captured=json.loads(rec_data.get("params_captured_json", "{}")),
                notes=rec_data.get("notes", ""),
            )
        return state

    def recent_summary(self, state: PipelineState) -> str:
        return f"会话 {state.session_id or 'unknown'}，已完成 {len(state.completed)} 个检查站，当前阶段 {state.current_cp_id}。"
