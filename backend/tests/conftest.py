import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app import storage
from backend.app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(storage, "DATA_DIR", data)
    monkeypatch.setattr(storage, "STATE_FILE", data / "demo_state.json")
    monkeypatch.setattr(storage, "ATTRACTIONS_FILE", data / "attractions.json")
    monkeypatch.setattr(storage, "MATRIX_FILE", data / "travel_times.json")
    monkeypatch.setattr(storage, "ensure_data", storage.ensure_data)
    with TestClient(app) as test_client:
        yield test_client
