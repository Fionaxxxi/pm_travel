from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
DATA_DIR = Path(os.environ.get("TRAVELMATE_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
STATE_FILE = DATA_DIR / "demo_state.json"
ATTRACTIONS_FILE = DATA_DIR / "attractions.json"
MATRIX_FILE = DATA_DIR / "travel_times.json"
SEED_STATE = CONTRACTS / "demo_state.seed.json"
SEED_ATTRACTIONS = CONTRACTS / "attractions.seed.json"
SEED_MATRIX = CONTRACTS / "travel_times.json"

_lock = threading.RLock()


def _read(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def seed_state() -> dict:
    return _read(SEED_STATE)


def ensure_data() -> None:
    with _lock:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not STATE_FILE.exists():
            _write_atomic(STATE_FILE, seed_state())
        if not ATTRACTIONS_FILE.exists():
            _write_atomic(ATTRACTIONS_FILE, _read(SEED_ATTRACTIONS))
        if not MATRIX_FILE.exists():
            _write_atomic(MATRIX_FILE, _read(SEED_MATRIX))
        if not (DATA_DIR / "meta.json").exists():
            _write_atomic(DATA_DIR / "meta.json", {"lastConfirmedId": None, "lastDiscardedId": None, "nextTrip": 1, "nextProposal": 1, "nextAttraction": 15, "nextNode": 1})


def read_state() -> dict:
    with _lock:
        ensure_data()
        return copy.deepcopy(_read(STATE_FILE))


def read_attractions() -> list[dict]:
    with _lock:
        ensure_data()
        return copy.deepcopy(_read(ATTRACTIONS_FILE)["items"])


def read_matrix() -> dict:
    with _lock:
        ensure_data()
        return copy.deepcopy(_read(MATRIX_FILE))


def read_meta() -> dict:
    with _lock:
        ensure_data()
        return copy.deepcopy(_read(DATA_DIR / "meta.json"))


def save_state(state: dict) -> None:
    with _lock:
        ensure_data()
        _write_atomic(STATE_FILE, state)


def save_attractions(items: list[dict]) -> None:
    with _lock:
        ensure_data()
        _write_atomic(ATTRACTIONS_FILE, {"datasetId": "prototype-shangrila-v1", "source": "user-prototype-html", "items": items})


def save_matrix(matrix: dict) -> None:
    with _lock:
        ensure_data()
        _write_atomic(MATRIX_FILE, matrix)


def save_meta(meta: dict) -> None:
    with _lock:
        ensure_data()
        _write_atomic(DATA_DIR / "meta.json", meta)


def reset_all() -> dict:
    with _lock:
        ensure_data()
        state = seed_state()
        _write_atomic(STATE_FILE, state)
        _write_atomic(ATTRACTIONS_FILE, _read(SEED_ATTRACTIONS))
        _write_atomic(MATRIX_FILE, _read(SEED_MATRIX))
        _write_atomic(DATA_DIR / "meta.json", {"lastConfirmedId": None, "lastDiscardedId": None, "nextTrip": 1, "nextProposal": 1, "nextAttraction": 15, "nextNode": 1})
        return copy.deepcopy(state)


def transaction() -> threading.RLock:
    """Single-process write lock; not a multi-process database lock."""
    return _lock
