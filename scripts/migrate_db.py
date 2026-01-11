#!/usr/bin/env python
from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "ocr.db"


def migrate_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    new_columns = [
        ("llm_model", "VARCHAR(100)"),
        ("property_type", "VARCHAR(100)"),
        ("property_name", "VARCHAR(200)"),
        ("room_number", "VARCHAR(50)"),
        ("address", "VARCHAR(500)"),
        ("prefecture", "VARCHAR(50)"),
        ("city", "VARCHAR(100)"),
        ("town", "VARCHAR(100)"),
        ("current_status", "VARCHAR(100)"),
        ("handover_date", "VARCHAR(50)"),
        ("is_renovated", "VARCHAR(10)"),
        ("renovation_date", "VARCHAR(50)"),
        ("year_built", "INTEGER"),
        ("structure", "VARCHAR(100)"),
        ("total_floors", "INTEGER"),
        ("floor_number", "INTEGER"),
        ("room_layout", "VARCHAR(50)"),
        ("orientation", "VARCHAR(50)"),
        ("price", "INTEGER"),
        ("management_fee", "INTEGER"),
        ("repair_fund", "INTEGER"),
        ("exclusive_area", "REAL"),
        ("land_area", "REAL"),
        ("building_area", "REAL"),
        ("balcony_area", "REAL"),
        ("nearest_station", "VARCHAR(200)"),
        ("nearest_line", "VARCHAR(200)"),
        ("walking_time", "INTEGER"),
        ("multiple_stations", "VARCHAR(10)"),
        ("has_parking", "VARCHAR(10)"),
        ("shopping_nearby", "TEXT"),
        ("pets_allowed", "VARCHAR(10)"),
    ]

    cursor.execute("PRAGMA table_info(documents)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            try:
                cursor.execute(
                    f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}"
                )
                print(f"Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"Error adding column {column_name}: {e}")

    conn.commit()
    conn.close()
    print("Database migration completed.")


if __name__ == "__main__":
    migrate_database()
