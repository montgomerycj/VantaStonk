"""
Test that new database schema tables exist.
"""

import sqlite3
from pathlib import Path
from src.db import init_db, get_connection


def test_new_tables_exist(tmp_path):
    """Verify that the four new v2 tables exist in the schema."""
    db = tmp_path / "t.db"
    init_db(str(db))
    conn = get_connection(str(db))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}

    assert "prompt_pulse_components" in names
    assert "ai_samples_raw" in names
    assert "social_snapshots" in names
    assert "recommendation_outcomes" in names

    conn.close()
