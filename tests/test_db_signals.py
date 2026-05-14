from datetime import datetime, timedelta
from src.db import (
    init_db, get_connection,
    save_prompt_pulse_components, get_recent_components,
)

def _setup(tmp_path):
    db = tmp_path / "t.db"
    init_db(str(db))
    return get_connection(str(db))

def test_save_and_retrieve_components(tmp_path):
    conn = _setup(tmp_path)
    now = datetime.now().isoformat(timespec="seconds")
    save_prompt_pulse_components(
        conn, ticker="ABCD", captured_at=now, scan_type="premarket",
        ai_sampling=0.8, social_velocity=0.4, volume_anomaly=0.6, composite=0.72,
    )
    rows = get_recent_components(conn, "ABCD", limit=5)
    assert len(rows) == 1
    assert rows[0]["composite"] == 0.72
    assert rows[0]["ai_sampling"] == 0.8
