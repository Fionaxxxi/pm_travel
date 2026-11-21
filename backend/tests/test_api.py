from copy import deepcopy
from datetime import datetime, timedelta
from backend.app import storage
from fastapi.testclient import TestClient
from backend.app.main import app


def payload(client, method, path, **kwargs):
    response = getattr(client, method)(path, **kwargs)
    return response, response.json()


def test_health_and_contract_shape(client):
    response, body = payload(client, "get", "/api/health")
    assert response.status_code == 200
    assert body["data"] == {"status": "ok", "contractVersion": "1.0.0"}
    invalid, body = payload(client, "put", "/api/profile", json={"profile": {}, "conditions": {}, "unexpected": True})
    assert invalid.status_code == 400
    assert body["message"] == "请求内容不符合接口约定"


def test_profile_persists_and_conditions_guard(client):
    state = client.get("/api/state").json()["data"]
    profile = deepcopy(state["profile"])
    profile["interests"]["nature"] = 0.9
    saved = client.put("/api/profile", json={"profile": profile, "conditions": state["conditions"]})
    assert saved.status_code == 200
    assert client.get("/api/state").json()["data"]["profile"]["interests"]["nature"] == 0.9
    assert client.post("/api/plan", json={"mode": "generate", "attractionIds": []}).status_code == 200
    state = client.get("/api/state").json()["data"]
    new_conditions = deepcopy(state["conditions"])
    new_conditions["budgetYuan"] += 10
    rejected = client.put("/api/profile", json={"profile": state["profile"], "conditions": new_conditions})
    assert rejected.status_code == 409


def test_state_survives_a_new_application_session(client):
    state = client.get("/api/state").json()["data"]
    state["profile"]["interests"]["food"] = 0.95
    assert client.put("/api/profile", json={"profile":state["profile"],"conditions":state["conditions"]}).status_code == 200
    state = client.post("/api/plan", json={"mode":"generate","attractionIds":["a01","a02","a03"]}).json()["data"]
    proposal_response = client.post("/api/replan", json={"events":[{"type":"delay","minutes":40}],"now":state["runtime"]["now"],"point":state["runtime"]["point"]})
    assert proposal_response.status_code == 200
    proposal_id = proposal_response.json()["data"]["proposal"]["id"]
    with TestClient(app) as restarted:
        recovered = restarted.get("/api/state").json()["data"]
    assert recovered["profile"]["interests"]["food"] == 0.95
    assert recovered["proposal"]["id"] == proposal_id
    assert recovered["trip"]["id"] == state["trip"]["id"]


def test_recommendation_changes_with_interest_and_is_deterministic(client):
    first = client.post("/api/recommend", json={}).json()["data"]["items"]
    state = client.get("/api/state").json()["data"]
    state["profile"]["interests"] = {"history": 0.05, "nature": 1.0, "food": 0.0}
    saved = client.put("/api/profile", json={"profile": state["profile"], "conditions": state["conditions"]})
    assert saved.status_code == 200
    second = client.post("/api/recommend", json={}).json()["data"]["items"]
    assert first[0]["attractionId"] != second[0]["attractionId"]
    assert second == client.post("/api/recommend", json={}).json()["data"]["items"]


def test_attraction_create_update_filter_and_matrix(client):
    original = client.get("/api/attractions").json()["data"]["items"]
    item = deepcopy(original[0])
    item.pop("id")
    item["name"] = "新增演示展馆"
    response = client.post("/api/attractions", json=item)
    assert response.status_code == 200
    created = response.json()["data"]
    assert created["id"] == "a15"
    matrix = storage.read_matrix()["minutes"]
    assert matrix["a15"]["a01"] == matrix["a01"]["a15"]
    assert matrix["a15"]["a15"] == 0
    assert client.get("/api/attractions?category=history").status_code == 200
    assert client.get("/api/attractions?category=photography").status_code == 200
    created["ticketYuan"] = 12
    update = client.put("/api/attractions", json=created)
    assert update.status_code == 200
    bad = deepcopy(created)
    bad["ticketYuan"] = -2
    assert client.put("/api/attractions", json=bad).status_code == 400


def test_attraction_field_boundaries_reject_invalid_and_allow_correction(client):
    original = client.get("/api/attractions").json()["data"]["items"][0]
    invalid_cases = []
    for field, value in [
        ("name", ""), ("name", "景" * 81), ("category", "other"),
        ("tags", []), ("tags", ["history", "history"]),
        ("point", {"lat": 91, "lng": 120.16}),
        ("point", {"lat": 30.25, "lng": -181}),
        ("openTime", "24:00"), ("closeTime", "17:60"),
        ("ticketYuan", -0.01), ("stayMinutes", 9), ("stayMinutes", 241),
        ("indoor", "yes"), ("intensity", "extreme"), ("enabled", "yes"),
        ("knowledgeText", ""), ("sources", []),
    ]:
        case = deepcopy(original)
        case[field] = value
        invalid_cases.append(case)
    missing_guide = deepcopy(original)
    del missing_guide["presetGuides"]["food"]
    invalid_cases.append(missing_guide)
    unknown_field = deepcopy(original)
    unknown_field["unexpected"] = True
    invalid_cases.append(unknown_field)

    for case in invalid_cases:
        response = client.put("/api/attractions", json=case)
        assert response.status_code == 400
    assert client.get("/api/attractions").json()["data"]["items"][0] == original

    corrected = deepcopy(original)
    corrected["name"] = "修正后的演示地点"
    corrected["ticketYuan"] = 12
    corrected["stayMinutes"] = 75
    response = client.put("/api/attractions", json=corrected)
    assert response.status_code == 200
    saved = client.get("/api/attractions").json()["data"]["items"][0]
    assert saved["name"] == corrected["name"]
    assert saved["ticketYuan"] == 12 and saved["stayMinutes"] == 75


def test_planning_time_budget_day_limit_and_edit_conflict(client):
    state = client.get("/api/state").json()["data"]
    state["conditions"]["days"] = 1
    state["conditions"]["budgetYuan"] = 1000
    assert client.put("/api/profile", json={"profile": state["profile"], "conditions": state["conditions"]}).status_code == 200
    result = client.post("/api/plan", json={"mode": "generate", "attractionIds": []})
    assert result.status_code == 200
    trip = result.json()["data"]["trip"]
    assert 1 <= len(trip["nodes"]) <= 4
    assert trip["estimatedTicketYuan"] <= result.json()["data"]["conditions"]["budgetYuan"]
    attractions = {a["id"]:a for a in client.get("/api/attractions").json()["data"]["items"]}
    for node in trip["nodes"]:
        assert node["arriveAt"].endswith("+08:00")
        assert node["leaveAt"] > node["startAt"]
        assert node["status"] == "pending"
        place = attractions[node["attractionId"]]
        assert node["startAt"][11:16] >= place["openTime"]
        assert node["leaveAt"][11:16] <= min(place["closeTime"], result.json()["data"]["conditions"]["dayEnd"])
    state = result.json()["data"]
    node = state["trip"]["nodes"][0]
    arrived = client.post("/api/trip/status", json={"nodeId": node["id"], "action": "arrive", "at": state["runtime"]["now"]})
    assert arrived.status_code == 200
    edit = client.post("/api/plan", json={"mode": "edit", "attractionIds": ["a03"]})
    assert edit.status_code == 409
    assert client.post("/api/plan", json={"mode":"generate","attractionIds":["a01","a01"]}).status_code == 400
    assert client.post("/api/plan", json={"mode":"generate","attractionIds":["unknown"]}).status_code == 400


def test_two_day_plan_rolls_a_full_stop_to_next_day(client):
    state = client.get("/api/state").json()["data"]
    state["conditions"]["days"] = 2
    state["conditions"]["dayEnd"] = "12:15"
    state["conditions"]["budgetYuan"] = 1000
    assert client.put("/api/profile", json={"profile":state["profile"],"conditions":state["conditions"]}).status_code == 200
    response = client.post("/api/plan", json={"mode":"generate","attractionIds":["a01","a02","a04"]})
    assert response.status_code == 200
    nodes = response.json()["data"]["trip"]["nodes"]
    assert [n["dayIndex"] for n in nodes] == [1, 1, 2]
    assert nodes[-1]["startAt"].startswith("2026-11-19T")


def test_two_day_replan_keeps_each_day_sequential(client):
    state = client.get("/api/state").json()["data"]
    state["conditions"]["days"] = 2
    state["conditions"]["budgetYuan"] = 1000
    assert client.put("/api/profile", json={"profile":state["profile"],"conditions":state["conditions"]}).status_code == 200
    planned = client.post("/api/plan", json={"mode":"generate","attractionIds":[f"a{i:02d}" for i in range(1, 9)]}).json()["data"]
    first = planned["trip"]["nodes"][0]
    arrived = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"arrive","at":first["arriveAt"]}).json()["data"]
    completed = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"complete","at":first["leaveAt"]}).json()["data"]
    request = {"events":[{"type":"fatigue"}],"now":completed["runtime"]["now"],"point":completed["runtime"]["point"]}
    result = client.post("/api/replan", json=request)
    assert result.status_code == 200
    nodes = result.json()["data"]["proposal"]["trip"]["nodes"]
    day_two = [node for node in nodes if node["dayIndex"] == 2]
    assert len(day_two) >= 2
    for previous, current in zip(day_two, day_two[1:]):
        previous_leave = datetime.fromisoformat(previous["leaveAt"])
        current_arrival = datetime.fromisoformat(current["arriveAt"])
        assert current_arrival >= previous_leave + timedelta(minutes=current["travelMinutes"])


def test_infeasible_plan_keeps_previous_state_unchanged(client):
    state = client.get("/api/state").json()["data"]
    state["conditions"]["budgetYuan"] = 0
    assert client.put("/api/profile", json={"profile":state["profile"],"conditions":state["conditions"]}).status_code == 200
    before = client.get("/api/state").json()["data"]
    response = client.post("/api/plan", json={"mode":"generate","attractionIds":["a03"]})
    assert response.status_code == 422
    assert client.get("/api/state").json()["data"] == before


def test_status_transitions_and_history_preserved_by_confirmed_replan(client):
    state = client.post("/api/plan", json={"mode": "generate", "attractionIds": ["a01", "a02", "a03"]}).json()["data"]
    first = state["trip"]["nodes"][0]
    arrived = client.post("/api/trip/status", json={"nodeId": first["id"], "action": "arrive", "at": state["runtime"]["now"]}).json()["data"]
    # At is monotonic and can equal arrival for this state-machine demonstration.
    completed = client.post("/api/trip/status", json={"nodeId": first["id"], "action": "complete", "at": arrived["runtime"]["now"]}).json()["data"]
    replay = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"complete","at":arrived["runtime"]["now"]})
    assert replay.status_code == 200 and replay.json()["data"] == completed
    assert client.post("/api/trip/status", json={"nodeId":first["id"],"action":"skip","at":arrived["runtime"]["now"]}).status_code == 409
    before_trip = deepcopy(completed["trip"])
    request = {"events": [{"type": "delay", "minutes": 40}], "now": completed["runtime"]["now"], "point": completed["runtime"]["point"]}
    candidate = client.post("/api/replan", json=request)
    assert candidate.status_code == 200
    proposed = candidate.json()["data"]
    assert proposed["trip"]["nodes"][0]["status"] == "completed"
    assert proposed["trip"]["nodes"][0]["id"] == before_trip["nodes"][0]["id"]
    assert client.get("/api/state").json()["data"]["trip"] == before_trip
    discarded = client.post("/api/replan/discard", json={"proposalId": proposed["proposal"]["id"]})
    assert discarded.status_code == 200
    assert discarded.json()["data"]["runtime"] == completed["runtime"]
    proposal = client.post("/api/replan", json=request).json()["data"]["proposal"]
    confirmed = client.post("/api/replan/confirm", json={"proposalId": proposal["id"]})
    assert confirmed.status_code == 200
    after = confirmed.json()["data"]
    assert after["trip"]["nodes"][0]["id"] == before_trip["nodes"][0]["id"]
    assert after["trip"]["nodes"][0]["status"] == "completed"
    assert after["runtime"]["now"] == "2026-11-18T09:40:00+08:00"
    assert client.post("/api/replan/confirm", json={"proposalId": proposal["id"]}).status_code == 200
    assert client.post("/api/replan/discard", json={"proposalId": "stale"}).status_code == 409


def test_replan_weather_fatigue_closed_and_no_solution(client):
    state = client.post("/api/plan", json={"mode": "generate", "attractionIds": ["a01", "a02", "a03", "a04"]}).json()["data"]
    node = state["trip"]["nodes"][0]
    state = client.post("/api/trip/status", json={"nodeId": node["id"], "action": "arrive", "at": state["runtime"]["now"]}).json()["data"]
    state = client.post("/api/trip/status", json={"nodeId": node["id"], "action": "complete", "at": state["runtime"]["now"]}).json()["data"]
    request = {"events": [{"type": "rain"}, {"type": "fatigue"}], "now": state["runtime"]["now"], "point": state["runtime"]["point"]}
    result = client.post("/api/replan", json=request)
    assert result.status_code == 200
    proposal = result.json()["data"]["proposal"]
    assert proposal["runtimeAfter"]["rain"] and proposal["runtimeAfter"]["fatigued"]
    for node in proposal["trip"]["nodes"]:
        if node["status"] == "pending":
            a = next(x for x in client.get("/api/attractions").json()["data"]["items"] if x["id"] == node["attractionId"])
            assert a["indoor"] and a["intensity"] != "high"
    # Duplicate event types are a request error and do not mutate the approved trip.
    bad = dict(request, events=[{"type":"rain"},{"type":"rain"}])
    assert client.post("/api/replan", json=bad).status_code == 400


def test_closed_attraction_is_removed_only_after_candidate_confirmation(client):
    state = client.post("/api/plan", json={"mode":"generate","attractionIds":["a01","a02","a03"]}).json()["data"]
    first = state["trip"]["nodes"][0]
    state = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"arrive","at":state["runtime"]["now"]}).json()["data"]
    state = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"complete","at":state["runtime"]["now"]}).json()["data"]
    target = next(n for n in state["trip"]["nodes"] if n["attractionId"] == "a02")
    before = deepcopy(state["trip"])
    request = {"events":[{"type":"closed","attractionId":"a02"}],"now":state["runtime"]["now"],"point":state["runtime"]["point"]}
    response = client.post("/api/replan", json=request)
    assert response.status_code == 200
    proposed = response.json()["data"]["proposal"]
    assert "a02" in proposed["runtimeAfter"]["closedAttractionIds"]
    assert "a02" not in [n["attractionId"] for n in proposed["trip"]["nodes"]]
    assert client.get("/api/state").json()["data"]["trip"] == before
    assert client.post("/api/replan/confirm", json={"proposalId":proposed["id"]}).status_code == 200
    assert client.get("/api/state").json()["data"]["trip"]["nodes"][0]["id"] == first["id"]
    assert target["status"] == "pending"


def test_unfeasible_replan_preserves_trip_and_runtime(client):
    state = client.post("/api/plan", json={"mode":"generate","attractionIds":["a01","a02"]}).json()["data"]
    first = state["trip"]["nodes"][0]
    state = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"arrive","at":first["arriveAt"]}).json()["data"]
    state = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"complete","at":first["leaveAt"]}).json()["data"]
    before_trip, before_runtime = deepcopy(state["trip"]), deepcopy(state["runtime"])
    request = {"events":[{"type":"delay","minutes":40}],"now":"2026-11-18T16:59:00+08:00","point":state["runtime"]["point"]}
    response = client.post("/api/replan", json=request)
    assert response.status_code == 422
    after = client.get("/api/state").json()["data"]
    assert after["trip"] == before_trip
    assert after["runtime"] == before_runtime
    assert after["proposal"] is None


def test_preset_guide_differs_by_depth_interest_and_marks_mock(client):
    short = client.post("/api/guide", json={"attractionId":"a01","depth":"detailed","availableMinutes":2}).json()["data"]
    assert short["effectiveDepth"] == "short"
    assert short["sourceMode"] == "preset" and short["degraded"] is False
    detailed = client.post("/api/guide", json={"attractionId":"a01","depth":"detailed","availableMinutes":60}).json()["data"]
    assert detailed["effectiveDepth"] == "detailed" and len(detailed["text"]) > len(short["text"])
    state = client.get("/api/state").json()["data"]
    state["profile"]["interests"] = {"history":0.1,"nature":0.9,"food":0.2}
    client.put("/api/profile", json={"profile":state["profile"],"conditions":state["conditions"]})
    nature = client.post("/api/guide", json={"attractionId":"a01","depth":"short","availableMinutes":60}).json()["data"]
    assert "自然" in nature["text"]


def test_nearby_ignore_disable_and_enable(client):
    result = client.post("/api/nearby", json={"action":"query"}).json()["data"]
    assert result["distanceKind"] == "straight_line"
    assert result["radiusMeters"] == 3000 and len(result["items"]) <= 3
    aid = result["items"][0]["attractionId"]
    ignored = client.post("/api/nearby", json={"action":"ignore","attractionId":aid}).json()["data"]
    assert aid in ignored["ignoredAttractionIds"]
    assert aid not in [x["attractionId"] for x in ignored["items"]]
    disabled = client.post("/api/nearby", json={"action":"set_enabled","enabled":False}).json()["data"]
    assert disabled["items"] == [] and not disabled["enabled"]
    enabled = client.post("/api/nearby", json={"action":"set_enabled","enabled":True}).json()["data"]
    assert enabled["enabled"] and aid in enabled["ignoredAttractionIds"]


def test_feedback_updates_once_and_conflicts_on_reused_request_id(client):
    state = client.get("/api/state").json()["data"]
    before = state["profile"]["interests"]["history"]
    request = {"requestId":"user-feedback-1","kind":"like","attractionId":"a01"}
    result = client.post("/api/feedback", json=request).json()["data"]
    assert result["record"]["after"]["interests"]["history"] == min(1, round(before + .1, 2))
    duplicate = client.post("/api/feedback", json=request).json()["data"]
    assert duplicate["duplicate"] is True
    assert duplicate["state"]["profile"] == result["state"]["profile"]
    reused = client.post("/api/feedback", json={**request,"kind":"dislike"})
    assert reused.status_code == 409
    tired = client.post("/api/feedback", json={"requestId":"user-feedback-2","kind":"too_tiring"}).json()["data"]
    assert tired["state"]["profile"]["pace"] == "relaxed"
    guide = client.post("/api/feedback", json={"requestId":"user-feedback-3","kind":"too_long"}).json()["data"]
    assert guide["state"]["profile"]["guideDepth"] == "short"


def test_reset_restores_seed_after_local_edits(client):
    state = client.get("/api/state").json()["data"]
    original = deepcopy(state)
    state["profile"]["interests"]["history"] = 0.1
    client.put("/api/profile", json={"profile":state["profile"],"conditions":state["conditions"]})
    attraction = deepcopy(client.get("/api/attractions").json()["data"]["items"][0])
    attraction.pop("id")
    attraction["name"] = "重置后应消失的地点"
    assert client.post("/api/attractions", json=attraction).status_code == 200
    reset = client.post("/api/reset", json={"confirm":"RESET_DEMO"})
    assert reset.status_code == 200
    assert reset.json()["data"] == original
    assert len(client.get("/api/attractions").json()["data"]["items"]) == 14


def test_end_to_end_preference_to_recommendation_and_adjustment_loop(client):
    state = client.get("/api/state").json()["data"]
    state["profile"]["interests"] = {"history":0.9,"nature":0.3,"food":0.4}
    state["profile"]["pace"] = "relaxed"
    state["profile"]["guideDepth"] = "short"
    assert client.put("/api/profile", json={"profile":state["profile"],"conditions":state["conditions"]}).status_code == 200
    ranked = client.post("/api/recommend", json={}).json()["data"]["items"]
    assert ranked and ranked[0]["reasons"]
    state = client.post("/api/plan", json={"mode":"generate","attractionIds":[]}).json()["data"]
    first = state["trip"]["nodes"][0]
    state = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"arrive","at":first["arriveAt"]}).json()["data"]
    state = client.post("/api/trip/status", json={"nodeId":first["id"],"action":"complete","at":first["leaveAt"]}).json()["data"]
    request = {"events":[{"type":"delay","minutes":40},{"type":"fatigue"}],"now":state["runtime"]["now"],"point":state["runtime"]["point"]}
    candidate = client.post("/api/replan", json=request).json()["data"]["proposal"]
    assert candidate["runtimeAfter"]["fatigued"] is True
    expected_now = (datetime.fromisoformat(state["runtime"]["now"]) + timedelta(minutes=40)).isoformat(timespec="seconds")
    assert candidate["runtimeAfter"]["now"] == expected_now
    assert candidate["trip"]["nodes"][0]["id"] == first["id"]
    assert client.post("/api/replan/discard", json={"proposalId":candidate["id"]}).status_code == 200
    candidate = client.post("/api/replan", json=request).json()["data"]["proposal"]
    state = client.post("/api/replan/confirm", json={"proposalId":candidate["id"]}).json()["data"]
    guide = client.post("/api/guide", json={"attractionId":first["attractionId"],"depth":"short","availableMinutes":60}).json()["data"]
    assert guide["sourceMode"] == "preset" and guide["text"]
    nearby = client.post("/api/nearby", json={"action":"query"}).json()["data"]
    assert len(nearby["items"]) <= 3
    if nearby["items"]:
        first_nearby = nearby["items"][0]["attractionId"]
        ignored = client.post("/api/nearby", json={"action":"ignore","attractionId":first_nearby}).json()["data"]
        assert first_nearby in ignored["ignoredAttractionIds"]
    result = client.post("/api/feedback", json={"requestId":"e2e-like-1","kind":"like","attractionId":first["attractionId"]}).json()["data"]
    assert result["duplicate"] is False
    refreshed = client.post("/api/recommend", json={}).json()["data"]["items"]
    assert refreshed
    assert client.get("/api/state").json()["data"]["feedback"][-1]["requestId"] == "e2e-like-1"
