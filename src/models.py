import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
import json


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                upload_time TEXT NOT NULL,
                ocr_status TEXT DEFAULT 'pending',
                ocr_text TEXT,
                llm_status TEXT DEFAULT 'pending',
                properties TEXT,
                retry_count INTEGER DEFAULT 0,
                favorite INTEGER DEFAULT 0,
                extracted_model TEXT,
                image_width INTEGER,
                image_height INTEGER,
                file_hash TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                display_order INTEGER DEFAULT 0,
                show_in_tag INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS station_durations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_name TEXT NOT NULL,
                location_id INTEGER NOT NULL,
                duration INTEGER NOT NULL,
                UNIQUE(station_name, location_id),
                FOREIGN KEY(location_id) REFERENCES locations(id) ON DELETE CASCADE
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_durations_location_id ON station_durations(location_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_durations_station_name ON station_durations(station_name)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_durations_composite ON station_durations(station_name, location_id)"
        )
        conn.commit()
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN favorite INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN extracted_model TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN image_width INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN image_height INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE documents ADD COLUMN file_hash TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    def create_document(self, filename: str) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO documents (filename, upload_time) VALUES (?, ?)",
            (filename, datetime.now().isoformat()),
        )
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return doc_id

    def get_document(self, doc_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            doc = dict(row)
            if doc.get("properties") and doc["properties"].strip():
                try:
                    doc["properties"] = json.loads(doc["properties"])
                except (json.JSONDecodeError, TypeError):
                    doc["properties"] = {}
            else:
                doc["properties"] = {}
            doc["station_durations"] = self.get_doc_station_durations(doc_id)
            return doc
        return None

    def get_document_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE filename = ?", (filename,))
        row = cursor.fetchone()
        conn.close()
        if row:
            doc = dict(row)
            if doc.get("properties") and doc["properties"].strip():
                try:
                    doc["properties"] = json.loads(doc["properties"])
                except (json.JSONDecodeError, TypeError):
                    doc["properties"] = {}
            else:
                doc["properties"] = {}
            return doc
        return None

    def get_all_documents(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM documents ORDER BY favorite DESC, "
            "CASE WHEN llm_status = 'done' THEN 1 "
            "WHEN ocr_status = 'pending' OR llm_status = 'pending' THEN 2 "
            "WHEN ocr_status = 'processing' OR llm_status = 'processing' THEN 3 "
            "ELSE 4 END, upload_time DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        docs = []
        for row in rows:
            doc = dict(row)
            if doc.get("properties") and doc["properties"].strip():
                try:
                    doc["properties"] = json.loads(doc["properties"])
                except (json.JSONDecodeError, TypeError):
                    doc["properties"] = {}
            else:
                doc["properties"] = {}
            doc["station_durations"] = self.get_doc_station_durations(doc["id"])
            docs.append(doc)
        return docs

    def update_ocr_status(
        self, doc_id: int, status: str, ocr_text: Optional[str] = None
    ):
        conn = self._get_connection()
        if ocr_text is not None:
            conn.execute(
                "UPDATE documents SET ocr_status = ?, ocr_text = ? WHERE id = ?",
                (status, ocr_text, doc_id),
            )
        else:
            conn.execute(
                "UPDATE documents SET ocr_status = ? WHERE id = ?", (status, doc_id)
            )
        conn.commit()
        conn.close()

    def update_llm_status(
        self,
        doc_id: int,
        status: str,
        properties: Optional[dict] = None,
        extracted_model: str = None,
    ):
        conn = self._get_connection()
        if properties is not None:
            conn.execute(
                "UPDATE documents SET llm_status = ?, properties = ?, extracted_model = ? WHERE id = ?",
                (
                    status,
                    json.dumps(properties, ensure_ascii=False),
                    extracted_model,
                    doc_id,
                ),
            )
        else:
            conn.execute(
                "UPDATE documents SET llm_status = ?, extracted_model = ? WHERE id = ?",
                (status, extracted_model, doc_id),
            )
        conn.commit()
        conn.close()

    def increment_retry(self, doc_id: int):
        conn = self._get_connection()
        conn.execute(
            "UPDATE documents SET retry_count = retry_count + 1 WHERE id = ?", (doc_id,)
        )
        conn.commit()
        conn.close()

    def get_pending_documents(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM documents WHERE (ocr_status = 'pending' OR "
            "(ocr_status = 'done' AND llm_status = 'pending') OR "
            "(ocr_status = 'processing' AND retry_count < 5) OR "
            "(llm_status = 'processing' AND retry_count < 5)) "
            "ORDER BY favorite DESC, upload_time ASC LIMIT 10"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def toggle_favorite(self, doc_id: int) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT favorite FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if row:
            new_favorite = 1 if row["favorite"] == 0 else 0
            conn.execute(
                "UPDATE documents SET favorite = ? WHERE id = ?",
                (new_favorite, doc_id),
            )
            conn.commit()
            conn.close()
            return new_favorite
        conn.close()
        return 0

    def delete_document(self, doc_id: int, file_path: str = None):
        from pathlib import Path

        conn = self._get_connection()
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()

        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass

    def reset_llm_status(self, doc_id: int):
        conn = self._get_connection()
        conn.execute(
            "UPDATE documents SET llm_status = 'pending', properties = NULL WHERE id = ?",
            (doc_id,),
        )
        conn.commit()
        conn.close()

    def reset_ocr_status(self, doc_id: int):
        conn = self._get_connection()
        conn.execute(
            "UPDATE documents SET ocr_status = 'pending', ocr_text = NULL, llm_status = 'pending', properties = NULL WHERE id = ?",
            (doc_id,),
        )
        conn.commit()
        conn.close()

    def update_image_dimensions(self, doc_id: int, width: int, height: int):
        conn = self._get_connection()
        conn.execute(
            "UPDATE documents SET image_width = ?, image_height = ? WHERE id = ?",
            (width, height, doc_id),
        )
        conn.commit()
        conn.close()

    def update_file_hash(self, doc_id: int, file_hash: str):
        conn = self._get_connection()
        conn.execute(
            "UPDATE documents SET file_hash = ? WHERE id = ?",
            (file_hash, doc_id),
        )
        conn.commit()
        conn.close()

    def get_document_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE file_hash = ?", (file_hash,))
        row = cursor.fetchone()
        conn.close()
        if row:
            doc = dict(row)
            if doc.get("properties") and doc["properties"].strip():
                try:
                    doc["properties"] = json.loads(doc["properties"])
                except (json.JSONDecodeError, TypeError):
                    doc["properties"] = {}
            else:
                doc["properties"] = {}
            doc["station_durations"] = self.get_doc_station_durations(doc["id"])
            return doc
        return None

    def get_all_locations(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations ORDER BY display_order, id")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_location(self, name: str) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO locations (name, display_order) VALUES (?, COALESCE((SELECT MAX(display_order) + 1 FROM locations), 1))",
            (name,),
        )
        location_id = cursor.lastrowid
        conn.commit()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()
        conn.close()
        return (
            dict(row)
            if row
            else {"id": location_id, "name": name, "display_order": 1, "show_in_tag": 0}
        )

    def delete_location(self, location_id: int):
        conn = self._get_connection()
        conn.execute("DELETE FROM locations WHERE id = ?", (location_id,))
        conn.execute(
            "DELETE FROM station_durations WHERE location_id = ?", (location_id,)
        )
        conn.commit()
        conn.close()

    def update_location_display(self, location_id: int, show_in_tag: int):
        conn = self._get_connection()
        conn.execute(
            "UPDATE locations SET show_in_tag = ? WHERE id = ?",
            (show_in_tag, location_id),
        )
        conn.commit()
        conn.close()

    def reorder_locations(self, location_ids: list):
        conn = self._get_connection()
        for i, location_id in enumerate(location_ids):
            conn.execute(
                "UPDATE locations SET display_order = ? WHERE id = ?",
                (i + 1, location_id),
            )
        conn.commit()
        conn.close()

    def get_travel_times_for_station(self, station_name: str) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sd.*, l.name as location_name, l.show_in_tag
            FROM station_durations sd
            JOIN locations l ON sd.location_id = l.id
            WHERE sd.station_name = ?
            ORDER BY l.display_order, l.id
        """,
            (station_name,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_all_travel_times(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sd.*, l.name as location_name, l.show_in_tag
            FROM station_durations sd
            JOIN locations l ON sd.location_id = l.id
            ORDER BY sd.station_name, l.display_order, l.id
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_station_durations(self, station_name: str) -> list:
        return self.get_travel_times_for_station(station_name)

    def get_all_station_durations(self) -> list:
        return self.get_all_travel_times()

    def set_station_duration(self, station_name: str, location_id: int, duration: int):
        conn = self._get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO station_durations (station_name, location_id, duration)
            VALUES (?, ?, ?)
        """,
            (station_name, location_id, duration),
        )
        conn.commit()
        conn.close()

    def delete_station_duration(self, station_name: str, location_id: int):
        conn = self._get_connection()
        conn.execute(
            "DELETE FROM station_durations WHERE station_name = ? AND location_id = ?",
            (station_name, location_id),
        )
        conn.commit()
        conn.close()

    def get_doc_station_durations(self, doc_id: int) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT properties FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            try:
                props = json.loads(row["properties"])
                stations = props.get("stations", [])
                if stations and isinstance(stations, list):
                    all_durations = []
                    for station in stations:
                        station_name = station.get("name")
                        if (
                            station_name
                            and isinstance(station_name, str)
                            and station_name.strip()
                        ):
                            durations = self.get_station_durations(station_name)
                            all_durations.extend(durations)
                    return all_durations
            except (json.JSONDecodeError, TypeError, KeyError):
                pass
        return []
