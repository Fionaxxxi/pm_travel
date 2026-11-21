from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import TypeAdapter, ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from . import engine, guide as guide_service, storage

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger("travelmate")
JSON_OBJECT = TypeAdapter(dict[str, Any])
with (ROOT / "contracts" / "api-v1.json").open(encoding="utf-8") as f:
    OPENAPI = json.load(f)
CONTRACT_URI = "https://travelmate.local/contracts/api-v1.json"
CONTRACT_REGISTRY = Registry().with_resource(
    CONTRACT_URI,
    Resource.from_contents(OPENAPI, default_specification=DRAFT202012),
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.ensure_data()
    yield


app = FastAPI(title="旅伴 AI 本机 Demo API", version="1.0.0", lifespan=lifespan)
extra_cors = [origin.strip() for origin in os.environ.get("TRAVELMATE_EXTRA_CORS_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:5191", "http://localhost:5191", *extra_cors],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)

REQUEST_SCHEMAS = {
    "PUT /api/profile": "SaveProfile", "POST /api/attractions": "AttractionFields",
    "PUT /api/attractions": "SaveAttraction", "POST /api/plan": "PlanRequest",
    "POST /api/trip/status": "StatusRequest", "POST /api/replan": "ReplanRequest",
    "POST /api/replan/confirm": "ProposalRequest", "POST /api/replan/discard": "ProposalRequest",
    "POST /api/guide": "GuideRequest", "POST /api/nearby": "NearbyRequest",
    "POST /api/feedback": "FeedbackRequest", "POST /api/reset": "ResetRequest",
}


def _success(value: Any) -> dict:
    return {"data": value}


def _error(status: int, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"message": message, "details": details or {}})


@app.exception_handler(engine.ApiError)
async def api_error_handler(_: Request, exc: engine.ApiError):
    return _error(exc.status, exc.message, exc.details)


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception):
    # Keep local error details useful without leaking tracebacks into the product UI.
    LOGGER.exception("本机 Demo API 内部错误", exc_info=exc)
    return _error(500, "本机服务发生错误，请检查服务终端", {"type": type(exc).__name__})


def _validate(method: str, path: str, body: dict) -> None:
    name = REQUEST_SCHEMAS.get(f"{method} {path}")
    if not name:
        return
    schema = {"$ref": f"{CONTRACT_URI}#/components/schemas/{name}"}
    validator = Draft202012Validator(schema, registry=CONTRACT_REGISTRY, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(body), key=lambda e: list(map(str, e.absolute_path)))
    if errors:
        first = errors[0]
        path_text = ".".join(str(x) for x in first.absolute_path)
        detail = {"path": path_text, "reason": first.message}
        raise engine.ApiError(400, "请求内容不符合接口约定", detail)


async def _body(request: Request, method: str, path: str) -> dict:
    try:
        payload = JSON_OBJECT.validate_python(await request.json())
    except Exception:
        raise engine.ApiError(400, "请求内容必须是合法 JSON")
    _validate(method, path, payload)
    return payload


def _clean_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


@app.get("/api/health")
def health():
    return _success({"status": "ok", "contractVersion": "1.0.0"})


@app.get("/api/state")
def get_state():
    return _success(storage.read_state())


@app.put("/api/profile")
async def save_profile(request: Request):
    body = await _body(request, "PUT", "/api/profile")
    with storage.transaction():
        state = storage.read_state()
        if state["trip"] and body["conditions"] != state["conditions"]:
            raise engine.ApiError(409, "已有行程时不能修改出行日期、天数和预算，请先重置或重新开始旅行")
        if _minutes(body["conditions"]["dayStart"]) >= _minutes(body["conditions"]["dayEnd"]):
            raise engine.ApiError(400, "每日结束时间必须晚于开始时间")
        state["profile"] = body["profile"]
        state["conditions"] = body["conditions"]
        state["proposal"] = None
        if not state["trip"]:
            start = datetime.combine(date.fromisoformat(state["conditions"]["startDate"]), time.fromisoformat(state["conditions"]["dayStart"])).replace(tzinfo=timezone(timedelta(hours=8)))
            state["runtime"] = {"now": start.isoformat(timespec="seconds"), "point": state["conditions"]["startPoint"], "rain": False, "fatigued": False, "closedAttractionIds": []}
        storage.save_state(state)
        return _success(state)


def _minutes(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


@app.get("/api/attractions")
def list_attractions(category: str | None = None, enabled: bool | None = None):
    if category is not None and category not in ("history", "nature", "food", "photography"):
        raise engine.ApiError(400, "景点分类无效")
    items = storage.read_attractions()
    if category:
        items = [a for a in items if a["category"] == category or category in a["tags"]]
    if enabled is not None:
        items = [a for a in items if a["enabled"] is enabled]
    return _success({"items": items})


def _complete_attraction(fields: dict, aid: str) -> dict:
    value = {"id": aid, **fields}
    if _minutes(value["openTime"]) >= _minutes(value["closeTime"]):
        raise engine.ApiError(400, "景点闭园时间必须晚于开园时间")
    return value


def _matrix_add(aid: str, point: dict, attractions: list[dict]):
    matrix = storage.read_matrix()
    matrix.setdefault("minutes", {})[aid] = {}
    for item in attractions:
        other = item["id"]
        minutes = 0 if point == item["point"] else 15
        matrix["minutes"][aid][other] = minutes
        matrix.setdefault("minutes", {}).setdefault(other, {})[aid] = minutes
    matrix["minutes"][aid][aid] = 0
    if "start" in matrix["minutes"]:
        start_point = storage.read_state()["conditions"]["startPoint"]
        matrix["minutes"]["start"][aid] = 0 if start_point == point else 15
        matrix["minutes"][aid]["start"] = matrix["minutes"]["start"][aid]
    storage.save_matrix(matrix)


@app.post("/api/attractions")
async def create_attraction(request: Request):
    body = await _body(request, "POST", "/api/attractions")
    with storage.transaction():
        items = storage.read_attractions()
        meta = storage.read_meta()
        aid = f"a{meta['nextAttraction']:02d}"
        meta["nextAttraction"] += 1
        value = _complete_attraction(body, aid)
        items.append(value)
        _matrix_add(aid, value["point"], items[:-1])
        storage.save_attractions(items)
        storage.save_meta(meta)
        state = storage.read_state()
        state["proposal"] = None
        storage.save_state(state)
        return _success(value)


@app.put("/api/attractions")
async def update_attraction(request: Request):
    body = await _body(request, "PUT", "/api/attractions")
    with storage.transaction():
        items = storage.read_attractions()
        index = next((i for i, a in enumerate(items) if a["id"] == body["id"]), None)
        if index is None:
            raise engine.ApiError(404, "没有找到这个景点")
        value = _complete_attraction({k: v for k, v in body.items() if k != "id"}, body["id"])
        old_point = items[index]["point"]
        items[index] = value
        if old_point != value["point"]:
            _matrix_add(value["id"], value["point"], [x for x in items if x["id"] != value["id"]])
        storage.save_attractions(items)
        state = storage.read_state()
        state["proposal"] = None
        storage.save_state(state)
        return _success(value)


@app.post("/api/recommend")
def recommend():
    state, attractions = storage.read_state(), storage.read_attractions()
    items = engine.recommendations(state, attractions)
    return _success({"items": items, "emptyReason": None if items else "当前预算或开放条件下没有可推荐的景点，请调整条件。"})


@app.post("/api/plan")
async def make_plan(request: Request):
    body = await _body(request, "POST", "/api/plan")
    with storage.transaction():
        state, attractions = storage.read_state(), storage.read_attractions()
        requested_ids = body["attractionIds"]
        known_ids = {a["id"] for a in attractions}
        if len(requested_ids) != len(set(requested_ids)):
            raise engine.ApiError(400, "景点顺序中不能包含重复地点")
        if any(aid not in known_ids for aid in requested_ids):
            raise engine.ApiError(400, "景点顺序中包含未知地点")
        if body["mode"] == "generate":
            runtime = state["runtime"]
            start = datetime.combine(date.fromisoformat(state["conditions"]["startDate"]), time.fromisoformat(state["conditions"]["dayStart"])).replace(tzinfo=timezone(timedelta(hours=8)))
            state["runtime"] = {"now": start.isoformat(timespec="seconds"), "point": state["conditions"]["startPoint"], "rain": False, "fatigued": False, "closedAttractionIds": []}
            state["proposal"] = None
            state["ignoredAttractionIds"] = []
            ids = body["attractionIds"] or [r["attractionId"] for r in engine.recommendations(state, attractions)]
            trip, _ = engine.schedule(ids, state, attractions)
            state["trip"] = trip
        else:
            if not state["trip"]:
                raise engine.ApiError(409, "请先生成行程")
            if any(n["status"] != "pending" for n in state["trip"]["nodes"]):
                raise engine.ApiError(409, "行程开始后请通过重规划调整")
            ids = body["attractionIds"] or [r["attractionId"] for r in engine.recommendations(state, attractions)]
            trip, _ = engine.schedule(ids, state, attractions, base_trip={"id": state["trip"]["id"], "nodes": [], "estimatedTicketYuan": 0, "warnings": [], "transportSource": "demo_matrix", "routeKind": "schematic"})
            state["trip"] = trip
            state["proposal"] = None
        storage.save_state(state)
        return _success(state)


@app.post("/api/trip/status")
async def set_node_status(request: Request):
    body = await _body(request, "POST", "/api/trip/status")
    with storage.transaction():
        state, meta = storage.read_state(), storage.read_meta()
        trip = state["trip"]
        if not trip:
            raise engine.ApiError(409, "当前没有行程")
        node = next((n for n in trip["nodes"] if n["id"] == body["nodeId"]), None)
        if node is None:
            raise engine.ApiError(404, "行程中没有这个景点")
        at = datetime.fromisoformat(body["at"])
        now = datetime.fromisoformat(state["runtime"]["now"])
        action = body["action"]
        last_action = meta.setdefault("statusActions", {}).get(node["id"])
        if action in ("complete", "skip", "leave") and last_action == {"action": action, "at": body["at"]}:
            return _success(state)
        if at < now:
            raise engine.ApiError(409, "操作时间不能早于当前状态时间")
        if action == "arrive":
            if node["status"] != "pending" or any(n["status"] == "current" for n in trip["nodes"]):
                raise engine.ApiError(409, "当前景点状态不允许到达")
            node["status"], node["actualArrivalAt"] = "current", body["at"]
            state["runtime"]["point"] = node["point"]
        elif action == "complete":
            if node["status"] != "current" or at < datetime.fromisoformat(node["actualArrivalAt"]):
                raise engine.ApiError(409, "只有已到达的景点可以完成，且完成时间不能早于到达")
            node["status"], node["actualFinishedAt"] = "completed", body["at"]
            state["runtime"]["point"] = node["point"]
        elif action == "leave":
            if node["status"] != "current":
                raise engine.ApiError(409, "只有当前游览中的景点可以提前离开")
            node["status"], node["actualFinishedAt"] = "skipped", body["at"]
            state["runtime"]["point"] = node["point"]
        elif action == "skip":
            if node["status"] != "pending":
                raise engine.ApiError(409, "只有尚未开始的景点可以跳过")
            node["status"], node["actualFinishedAt"] = "skipped", body["at"]
        state["runtime"]["now"] = body["at"]
        state["proposal"] = None
        meta["statusActions"][node["id"]] = {"action": action, "at": body["at"]}
        storage.save_state(state)
        storage.save_meta(meta)
        return _success(state)


@app.post("/api/replan")
async def create_proposal(request: Request):
    body = await _body(request, "POST", "/api/replan")
    with storage.transaction():
        state = storage.read_state()
        state["proposal"] = None
        try:
            proposal = engine._replan(state, storage.read_attractions(), body)
        except engine.ApiError as exc:
            storage.save_state(state)
            raise exc
        state["proposal"] = proposal
        storage.save_state(state)
        return _success(state)


@app.post("/api/replan/confirm")
async def confirm_proposal(request: Request):
    body = await _body(request, "POST", "/api/replan/confirm")
    with storage.transaction():
        state, meta = storage.read_state(), storage.read_meta()
        proposal = state["proposal"]
        if not proposal:
            if meta.get("lastConfirmedId") == body["proposalId"]:
                return _success(state)
            raise engine.ApiError(409, "调整建议已失效，请重新生成")
        if proposal["id"] != body["proposalId"]:
            raise engine.ApiError(409, "调整建议编号不匹配")
        state["trip"], state["runtime"], state["proposal"] = proposal["trip"], proposal["runtimeAfter"], None
        meta["lastConfirmedId"] = body["proposalId"]
        storage.save_state(state)
        storage.save_meta(meta)
        return _success(state)


@app.post("/api/replan/discard")
async def discard_proposal(request: Request):
    body = await _body(request, "POST", "/api/replan/discard")
    with storage.transaction():
        state, meta = storage.read_state(), storage.read_meta()
        proposal = state["proposal"]
        if not proposal:
            if meta.get("lastDiscardedId") == body["proposalId"]:
                return _success(state)
            raise engine.ApiError(409, "调整建议已失效")
        if proposal["id"] != body["proposalId"]:
            raise engine.ApiError(409, "调整建议编号不匹配")
        state["proposal"] = None
        meta["lastDiscardedId"] = body["proposalId"]
        storage.save_state(state)
        storage.save_meta(meta)
        return _success(state)


@app.post("/api/guide")
async def guide(request: Request):
    body = await _body(request, "POST", "/api/guide")
    attraction = next((a for a in storage.read_attractions() if a["id"] == body["attractionId"]), None)
    if not attraction:
        raise engine.ApiError(404, "没有找到这个景点")
    state = storage.read_state()
    depth = "short" if body["availableMinutes"] <= 2 else body["depth"]
    interests = state["profile"]["interests"]
    strongest = max(engine.TAGS, key=lambda t: (interests[t], -engine.TAGS.index(t)))
    text = attraction["presetGuides"][strongest][depth]
    guide_mode = os.environ.get("GUIDE_MODE", "preset").strip().lower()
    generated, model = await guide_service.generate(attraction, strongest, depth, body["availableMinutes"]) if guide_mode == "llm" else (None, None)
    if generated:
        text = generated
        source_mode = "llm"
        degraded = False
        notice = f"AI 生成内容（{model}），仅依据景点资料整理；资料与事实尚未独立核验。"
    else:
        source_mode = "preset"
        degraded = guide_mode == "llm"
        notice = "模型暂不可用，已回退到预置解说；资料依据原型内置内容，尚未外部核验。" if degraded else "当前使用预置解说；资料依据原型内置内容，尚未外部核验。"
    return _success({"attractionId": attraction["id"], "depth": body["depth"], "effectiveDepth": depth, "text": text, "sources": attraction["sources"], "sourceMode": source_mode, "degraded": degraded, "notice": notice})


@app.post("/api/nearby")
async def nearby(request: Request):
    body = await _body(request, "POST", "/api/nearby")
    with storage.transaction():
        state = storage.read_state()
        if body["action"] == "ignore":
            aid = body["attractionId"]
            if not any(a["id"] == aid for a in storage.read_attractions()):
                raise engine.ApiError(404, "没有找到这个景点")
            if aid not in state["ignoredAttractionIds"]:
                state["ignoredAttractionIds"].append(aid)
            storage.save_state(state)
        elif body["action"] == "set_enabled":
            state["nearbyEnabled"] = body["enabled"]
            storage.save_state(state)
        return _success(engine.nearby_result(state, storage.read_attractions()))


@app.post("/api/feedback")
async def feedback(request: Request):
    body = await _body(request, "POST", "/api/feedback")
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    with storage.transaction():
        state, meta = storage.read_state(), storage.read_meta()
        requests = meta.setdefault("feedbackRequests", {})
        if body["requestId"] in requests:
            if requests[body["requestId"]]["hash"] != fingerprint:
                raise engine.ApiError(409, "相同请求编号不能用于不同反馈")
            old = next(r for r in state["feedback"] if r["requestId"] == body["requestId"])
            return _success({"record": old, "duplicate": True, "state": state})
        before = copy.deepcopy(state["profile"])
        after = copy.deepcopy(before)
        kind, aid = body["kind"], body.get("attractionId")
        if kind in ("like", "dislike"):
            attraction = next((a for a in storage.read_attractions() if a["id"] == aid), None)
            if not attraction:
                raise engine.ApiError(404, "没有找到这个景点")
            delta = .1 if kind == "like" else -.1
            for tag in attraction["tags"]:
                after["interests"][tag] = round(min(1, max(0, after["interests"][tag] + delta)), 2)
        elif kind == "too_tiring":
            after["pace"] = "relaxed"
        elif kind == "too_long":
            after["guideDepth"] = "short"
        record = {"requestId": body["requestId"], "kind": kind, "attractionId": aid, "before": before, "after": after}
        state["profile"] = after
        state["feedback"].append(record)
        state["proposal"] = None
        requests[body["requestId"]] = {"hash": fingerprint}
        storage.save_state(state)
        storage.save_meta(meta)
        return _success({"record": record, "duplicate": False, "state": state})


@app.post("/api/reset")
async def reset(request: Request):
    body = await _body(request, "POST", "/api/reset")
    if body["confirm"] != "RESET_DEMO":
        raise engine.ApiError(400, "重置确认内容无效")
    return _success(storage.reset_all())


