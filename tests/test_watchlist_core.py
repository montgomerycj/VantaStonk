from src.watchlist.core import (
    CoreEntry, load_core, save_core, add_core_entry, remove_core_entry, CORE_MAX,
)

def test_load_missing_returns_empty(tmp_path):
    p = tmp_path / "core.json"
    assert load_core(p) == []

def test_roundtrip(tmp_path):
    p = tmp_path / "core.json"
    entries = [
        CoreEntry(ticker="XYZ", thesis="Block rebrand",
                  added="2026-04-20", conviction="high", review_by="2026-05-20"),
    ]
    save_core(p, entries)
    assert load_core(p) == entries

def test_backup_written(tmp_path):
    p = tmp_path / "core.json"
    save_core(p, [CoreEntry(ticker="A", thesis="t", added="d", conviction="high", review_by="d")])
    save_core(p, [])  # second save should create a backup
    backups = list(tmp_path.glob("core.json.bak-*"))
    assert len(backups) == 1

def test_add_enforces_max(tmp_path):
    p = tmp_path / "core.json"
    entries = [
        CoreEntry(ticker=f"T{i}", thesis="x", added="d", conviction="high", review_by="d")
        for i in range(CORE_MAX)
    ]
    save_core(p, entries)
    try:
        add_core_entry(p, CoreEntry(ticker="NEW", thesis="x", added="d", conviction="high", review_by="d"))
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_remove(tmp_path):
    p = tmp_path / "core.json"
    save_core(p, [CoreEntry(ticker="A", thesis="t", added="d", conviction="high", review_by="d")])
    remove_core_entry(p, "A")
    assert load_core(p) == []
