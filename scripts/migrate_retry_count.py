#!/usr/bin/env python
"""数据库迁移：添加 OCR 重试计数字段"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "ocr.db"


def migrate_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(documents)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "ocr_retry_count" not in existing_columns:
        try:
            cursor.execute(
                "ALTER TABLE documents ADD COLUMN ocr_retry_count INTEGER DEFAULT 0"
            )
            print("✓ 已添加列: ocr_retry_count")
        except sqlite3.OperationalError as e:
            print(f"✗ 添加列失败: {e}")
    else:
        print("✓ 列 ocr_retry_count 已存在")

    conn.commit()
    conn.close()
    print("数据库迁移完成")


if __name__ == "__main__":
    migrate_database()
