#!/usr/bin/env python
"""数据库迁移：添加队列管理状态字段"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "ocr.db"


def migrate_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(documents)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ("ocr_status", "VARCHAR(20) DEFAULT 'pending'"),
        ("ocr_priority", "INTEGER DEFAULT 5"),
        ("ocr_error_message", "TEXT"),
        ("ocr_last_attempt", "DATETIME"),
        ("llm_status", "VARCHAR(20) DEFAULT 'pending'"),
        ("llm_priority", "INTEGER DEFAULT 5"),
        ("llm_error_message", "TEXT"),
        ("llm_last_attempt", "DATETIME"),
    ]

    for column_name, column_type in new_columns:
        if column_name not in existing_columns:
            try:
                cursor.execute(
                    f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}"
                )
                print(f"✓ 已添加列: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"✗ 添加列失败 {column_name}: {e}")
        else:
            print(f"✓ 列 {column_name} 已存在")

    conn.commit()
    conn.close()
    print("\n数据库迁移完成")


if __name__ == "__main__":
    migrate_database()
