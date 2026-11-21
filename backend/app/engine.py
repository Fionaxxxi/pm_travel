from __future__ import annotations

import copy
import math
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from . import storage

TAGS = ("history", "nature", "food")
PACE = {"relaxed": "轻松", "normal": "正常"}


class ApiError(Exception):
    def __init__(self, status: int, message: str, details: dict | None = None):
        self.status, self.message, self.details = status, message, details or {}


def _dt(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError(400, "日期时间格式无效")
    if parsed.utcoffset() != timedelta(hours=8):
        raise ApiError(400, "日期时间必须使用 +08:00 时区")
    return parsed


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _minutes(value: str) -> int:
    h, m = map(int, value.split(":"))
    return h * 60 + m


def _score(attraction: dict, profile: dict, fatigued: bool = False) -> float:
    score = sum(profile["interests"][tag] for tag in attraction["tags"]) / len(attraction["tags"])
    if (profile["pace"] == "relaxed" or fatigued) and attraction["intensity"] == "high":
        score -= 0.25
    return round(max(0.0, score), 4)


def recommendations(state: dict, attractions: list[dict], remaining_budget: float | None = None, runtime: dict | None = None, profile: dict | None = None) -> list[dict]:
    runtime = runtime or state["runtime"]
    profile = profile or state["profile"]
    budget = state["conditions"]["budgetYuan"] if remaining_budget is None else remaining_budget
    closed = set(runtime["closedAttractionIds"])
    now = _dt(runtime["now"])
    items = []
    for a in attractions:
        if not a["enabled"] or a["id"] in closed or a["ticketYuan"] > budget:
            continue
        if _minutes(a["closeTime"]) - _minutes(a["openTime"]) < a["stayMinutes"]:
            continue
        hits = [t for t in a["tags"] if profile["interests"][t] > 0]
        reasons = ([f"匹配{ '、'.join({'history':'历史文化','nature':'自然风光','food':'地方美食'}[x] for x in hits)}兴趣"] if hits else ["可作为不同主题的补充"]) \
            + (["室内，雨天也适合"] if a["indoor"] else []) \
            + (["强度较低，适合轻松游览"] if a["intensity"] == "low" else [])
        if now.strftime("%H:%M") >= a["closeTime"]:
            reasons.append("当前已过闭园时间")
        items.append({"attractionId": a["id"], "name": a["name"], "point": a["point"], "score": _score(a, profile, runtime["fatigued"]), "reasons": reasons, "stayMinutes": a["stayMinutes"], "ticketYuan": a["ticketYuan"]})
    return sorted(items, key=lambda x: (-x["score"], x["attractionId"]))


def _travel(matrix: dict, from_id: str | None, to_id: str, from_point: dict, to_point: dict) -> int:
    if from_point["lat"] == to_point["lat"] and from_point["lng"] == to_point["lng"]:
        return 0
    if from_id and from_id in matrix.get("minutes", {}) and to_id in matrix["minutes"][from_id]:
        return int(matrix["minutes"][from_id][to_id])
    return 15


def schedule(ids: list[str], state: dict, attractions: list[dict], start_at: datetime | None = None, start_point: dict | None = None, first_day_index: int = 1, base_trip: dict | None = None, excluded: set[str] | None = None) -> tuple[dict, list[str]]:
    conditions, matrix = state["conditions"], storage.read_matrix()
    by_id = {a["id"]: a for a in attractions}
    excluded = excluded or set()
    nodes = copy.deepcopy(base_trip["nodes"] if base_trip else [])
    warnings, omitted = [], []
    spent = sum(n["ticketYuan"] for n in nodes if n["status"] in ("current", "completed") or n.get("actualArrivalAt"))
    current_day = max(1, first_day_index)
    max_day = conditions["days"]
    if start_at is None:
        current_day = 1
        current_time = datetime.combine(date.fromisoformat(conditions["startDate"]), time.fromisoformat(conditions["dayStart"])).replace(tzinfo=timezone(timedelta(hours=8)))
        point = conditions["startPoint"]
    else:
        current_time, point = start_at, start_point or conditions["startPoint"]
    previous_id = None
    # Replanned first day begins at the confirmed user location; each later day starts at the configured start point.
    for aid in ids:
        if aid in excluded or aid not in by_id:
            omitted.append(aid)
            continue
        a = by_id[aid]
        if not a["enabled"] or aid in state["runtime"]["closedAttractionIds"]:
            omitted.append(aid)
            continue
        if spent + a["ticketYuan"] > conditions["budgetYuan"]:
            warnings.append(f"{a['name']}：超出剩余门票预算")
            omitted.append(aid)
            continue
        placed = False
        while current_day <= max_day:
            if sum(1 for n in nodes if n["dayIndex"] == current_day) >= 4:
                current_day += 1
                if current_day > max_day:
                    break
                day_date = date.fromisoformat(conditions["startDate"]) + timedelta(days=current_day - 1)
                current_time = datetime.combine(day_date, time.fromisoformat(conditions["dayStart"])).replace(tzinfo=current_time.tzinfo)
                point, previous_id = conditions["startPoint"], None
                continue
            travel = _travel(matrix, previous_id or "start", aid, point, a["point"])
            arrival = current_time + timedelta(minutes=travel)
            open_at = datetime.combine(arrival.date(), time.fromisoformat(a["openTime"])).replace(tzinfo=arrival.tzinfo)
            begin = max(arrival, open_at)
            finish = begin + timedelta(minutes=a["stayMinutes"])
            close_at = datetime.combine(begin.date(), time.fromisoformat(a["closeTime"])).replace(tzinfo=begin.tzinfo)
            day_end = datetime.combine(begin.date(), time.fromisoformat(conditions["dayEnd"])).replace(tzinfo=begin.tzinfo)
            if finish <= close_at and finish <= day_end:
                meta = storage.read_meta()
                node_id = f"n{meta['nextNode']:04d}"
                meta["nextNode"] += 1
                storage.save_meta(meta)
                nodes.append({"id": node_id, "attractionId": aid, "attractionName": a["name"], "point": a["point"], "dayIndex": current_day, "arriveAt": _iso(arrival), "startAt": _iso(begin), "leaveAt": _iso(finish), "travelMinutes": travel, "stayMinutes": a["stayMinutes"], "ticketYuan": a["ticketYuan"], "status": "pending", "actualArrivalAt": None, "actualFinishedAt": None})
                spent += a["ticketYuan"]
                current_time, point, previous_id = finish, a["point"], aid
                placed = True
                break
            current_day += 1
            if current_day <= max_day:
                day_date = date.fromisoformat(conditions["startDate"]) + timedelta(days=current_day - 1)
                current_time = datetime.combine(day_date, time.fromisoformat(conditions["dayStart"])).replace(tzinfo=current_time.tzinfo)
                point, previous_id = conditions["startPoint"], None
        if not placed:
            warnings.append(f"{a['name']}：在可安排日期与开放时间内放不下")
            omitted.append(aid)
            # Subsequent candidate should still get a fresh attempt on last available day if this attraction is too long.
            if current_day > max_day:
                break
    if not nodes:
        raise ApiError(422, "当前条件下没有可行景点，请调整时间、预算或旅行天数")
    meta = storage.read_meta()
    trip = {"id": base_trip["id"] if base_trip else f"trip-{meta['nextTrip']:04d}", "nodes": nodes, "estimatedTicketYuan": round(spent, 2), "warnings": warnings, "transportSource": "demo_matrix", "routeKind": "schematic"}
    if base_trip is None:
        meta["nextTrip"] += 1
        storage.save_meta(meta)
    return trip, omitted


def nearby_result(state: dict, attractions: list[dict]) -> dict:
    ignored = set(state["ignoredAttractionIds"])
    if not state["nearbyEnabled"]:
        items = []
    else:
        runtime, trip = state["runtime"], state["trip"]
        point = runtime["point"]
        excluded = ignored | set(runtime["closedAttractionIds"])
        if trip:
            excluded |= {n["attractionId"] for n in trip["nodes"] if n["status"] in ("completed", "skipped", "pending", "current")}
        profile, cond, now = state["profile"], state["conditions"], _dt(runtime["now"])
        item_list = []
        for a in attractions:
            if not a["enabled"] or a["id"] in excluded or (runtime["rain"] and not a["indoor"]) or (runtime["fatigued"] and a["intensity"] == "high"):
                continue
            lat1, lat2 = math.radians(point["lat"]), math.radians(a["point"]["lat"])
            dlat = lat2 - lat1
            dlon = math.radians(a["point"]["lng"] - point["lng"])
            hav = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            distance = round(6371000 * 2 * math.asin(math.sqrt(hav)))
            travel = 0 if distance == 0 else 15
            duration = travel + a["stayMinutes"]
            if distance > 3000:
                continue
            open_at = datetime.combine(now.date(), time.fromisoformat(a["openTime"])).replace(tzinfo=now.tzinfo)
            finish = max(now + timedelta(minutes=travel), open_at) + timedelta(minutes=a["stayMinutes"])
            end = datetime.combine(now.date(), time.fromisoformat(cond["dayEnd"])).replace(tzinfo=now.tzinfo)
            close = datetime.combine(now.date(), time.fromisoformat(a["closeTime"])).replace(tzinfo=now.tzinfo)
            if finish > min(end, close):
                continue
            item_list.append({"attractionId": a["id"], "name": a["name"], "distanceMeters": distance, "estimatedMinutes": duration, "reasons": ["距離較近", f"匹配{ {'history':'历史文化','nature':'自然风光','food':'地方美食'}[max(a['tags'], key=lambda t: profile['interests'][t])]}兴趣"]})
        items = sorted(item_list, key=lambda x: (-_score(next(a for a in attractions if a['id']==x['attractionId']), profile, runtime['fatigued']), x["distanceMeters"], x["attractionId"]))[:3]
    return {"enabled": state["nearbyEnabled"], "items": items, "ignoredAttractionIds": state["ignoredAttractionIds"], "radiusMeters": 3000, "distanceKind": "straight_line"}


def _trip_id_set(state: dict) -> set[str]:
    return {n["attractionId"] for n in (state["trip"] or {}).get("nodes", [])}


def _replan(state: dict, attractions: list[dict], request: dict) -> dict:
    trip = state["trip"]
    if not trip:
        raise ApiError(409, "请先生成行程")
    if any(n["status"] == "current" for n in trip["nodes"]):
        raise ApiError(409, "请先完成或离开当前景点")
    now = _dt(request["now"])
    runtime = copy.deepcopy(state["runtime"])
    if now < _dt(runtime["now"]):
        raise ApiError(409, "调整时间不能早于当前状态时间")
    events = request["events"]
    types = [e["type"] for e in events]
    if len(set(types)) != len(types):
        raise ApiError(400, "同一次调整不能重复提交相同类型事件")
    event_summary = []
    temp_profile = copy.deepcopy(state["profile"])
    delay = 0
    excluded = set()
    for event in events:
        typ = event["type"]
        if typ == "delay":
            delay = event["minutes"]
            event_summary.append(f"延误 {delay} 分钟")
        elif typ == "fatigue":
            runtime["fatigued"] = True
            event_summary.append("按轻松节奏重排")
        elif typ == "rain":
            runtime["rain"] = True
            event_summary.append("优先安排室内景点")
        elif typ == "closed":
            aid = event["attractionId"]
            if aid not in {n["attractionId"] for n in trip["nodes"] if n["status"] == "pending"}:
                raise ApiError(400, "关闭的景点必须是行程中的未完成景点")
            if aid not in runtime["closedAttractionIds"]:
                runtime["closedAttractionIds"].append(aid)
            excluded.add(aid)
            event_summary.append("移除临时关闭景点")
        elif typ == "interest_change":
            tag = event["interest"]
            temp_profile["interests"][tag] = min(1.0, round(temp_profile["interests"][tag] + .3, 2))
            event_summary.append("提高本次" + {"history":"历史文化", "nature":"自然风光", "food":"地方美食"}[tag] + "优先级")
    start_time = now + timedelta(minutes=delay)
    runtime_after = copy.deepcopy(runtime)
    runtime_after["now"] = _iso(start_time)
    runtime_after["point"] = request["point"]
    completed = [copy.deepcopy(n) for n in trip["nodes"] if n["status"] in ("completed", "skipped")]
    completed_ids = {n["attractionId"] for n in completed}
    remaining = [n["attractionId"] for n in trip["nodes"] if n["status"] == "pending" and n["attractionId"] not in excluded and n["attractionId"] not in completed_ids]
    remaining_set = set(remaining)
    ranking = recommendations({**state, "runtime": runtime_after}, attractions, max(0, state["conditions"]["budgetYuan"] - sum(n["ticketYuan"] for n in completed)), runtime_after, temp_profile)
    for r in ranking:
        if r["attractionId"] not in remaining_set and r["attractionId"] not in completed_ids and r["attractionId"] not in excluded:
            remaining.append(r["attractionId"])
    if runtime_after["rain"]:
        remaining = [aid for aid in remaining if next(a for a in attractions if a["id"] == aid)["indoor"]]
    if runtime_after["fatigued"]:
        remaining = [aid for aid in remaining if next(a for a in attractions if a["id"] == aid)["intensity"] != "high"]
    remaining = list(dict.fromkeys(remaining))
    day_index = max(1, min(state["conditions"]["days"], now.date().toordinal() - date.fromisoformat(state["conditions"]["startDate"]).toordinal() + 1))
    base = {"id": trip["id"], "nodes": completed, "estimatedTicketYuan": sum(n["ticketYuan"] for n in completed), "warnings": [], "transportSource": "demo_matrix", "routeKind": "schematic"}
    new_trip, omitted = schedule(remaining, state, attractions, start_time, request["point"], day_index, base, excluded)
    old_pending = {n["attractionId"] for n in trip["nodes"] if n["status"] == "pending"}
    new_pending = {n["attractionId"] for n in new_trip["nodes"] if n["status"] == "pending"}
    if old_pending and not new_pending:
        raise ApiError(422, "剩余时间内无法安排新的景点，请结束本次行程或放宽条件")
    removed = sorted((old_pending - new_pending) | excluded)
    added = sorted(new_pending - old_pending)
    reasons = event_summary or ["按当前条件重新安排剩余行程"]
    reasons += [f"未能安排：{', '.join(omitted)}"] if omitted else []
    meta = storage.read_meta()
    proposal_id = f"proposal-{meta['nextProposal']:04d}"
    meta["nextProposal"] += 1
    meta["lastDiscardedId"] = None
    storage.save_meta(meta)
    return {"id": proposal_id, "trip": new_trip, "reasons": reasons, "removedAttractionIds": removed, "addedAttractionIds": added, "runtimeAfter": runtime_after}
