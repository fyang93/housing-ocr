#!/usr/bin/env python3
"""Reset all LLM statuses to 'pending' to trigger reprocessing with updated prompt."""

import sqlite3
import sys
from pathlib import Path


def reset_llm_status(db_path: str):
    """Reset all documents' LLM status to pending."""
    if not Path(db_path).exists():
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check how many documents will be reset
        cursor.execute(
            "SELECT COUNT(*) FROM documents WHERE llm_status IN ('done', 'processing', 'failed')"
        )
        count = cursor.fetchone()[0]

        if count == 0:
            print("No documents need LLM status reset.")
            conn.close()
            return

        print(f"Found {count} document(s) with LLM status that will be reset.")
        confirm = input("Do you want to proceed? (y/N): ").strip().lower()

        if confirm != "y":
            print("Operation cancelled.")
            conn.close()
            return

        # Reset LLM status for all documents
        cursor.execute(
            "UPDATE documents SET llm_status = 'pending', properties = NULL, extracted_model = NULL"
        )
        conn.commit()

        print(f"✓ Successfully reset LLM status for {count} document(s).")
        print("  The processor will reprocess all documents with the updated prompt.")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path from config
    import tomli

    try:
        project_root = Path(__file__).parent.parent
        config_path = project_root / "config.toml"

        if not config_path.exists():
            print(
                "Warning: config.toml not found, using default database path: ./data.db"
            )
            db_path = "data.db"
        else:
            with open(config_path, "rb") as f:
                config = tomli.load(f)
            db_path = config["app"]["db_path"]
    except Exception as e:
        print(f"Warning: Could not load config: {e}")
        print("Using default database path: ./data.db")
        db_path = "data.db"

    reset_llm_status(db_path)
