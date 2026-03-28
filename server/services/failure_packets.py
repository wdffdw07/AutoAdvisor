from __future__ import annotations

from copy import deepcopy


def begin_failure_episode(step_id: str, failure_type: str, snapshot: dict) -> dict:
    snapshot = deepcopy(snapshot or {})
    return {
        "step_id": step_id,
        "failure_type": failure_type,
        "attempt_count": 0,
        "window_signature": deepcopy(snapshot.get("window_signature") or {}),
        "target_summary": deepcopy(snapshot.get("target_summary") or {}),
        "candidate_summary": deepcopy(snapshot.get("candidate_summary") or []),
        "recovery_actions": [],
        "outcome": snapshot.get("outcome", "pending"),
    }


def append_recovery_action(episode: dict, action: str, outcome: str) -> None:
    episode.setdefault("recovery_actions", []).append(
        {
            "action": action,
            "outcome": outcome,
        }
    )
    episode["attempt_count"] = len(episode["recovery_actions"])
    episode["outcome"] = outcome


def _merge_failure_episodes(episodes: list[dict]) -> list[dict]:
    merged = []
    for episode in episodes:
        current = deepcopy(episode)
        if merged and merged[-1]["step_id"] == current["step_id"] and merged[-1]["failure_type"] == current["failure_type"]:
            merged[-1]["attempt_count"] += current.get("attempt_count", 0)
            merged[-1]["recovery_actions"].extend(deepcopy(current.get("recovery_actions") or []))
            if current.get("candidate_summary"):
                merged[-1]["candidate_summary"] = deepcopy(current["candidate_summary"])
            if current.get("target_summary"):
                merged[-1]["target_summary"] = deepcopy(current["target_summary"])
            if current.get("window_signature"):
                merged[-1]["window_signature"] = deepcopy(current["window_signature"])
            merged[-1]["outcome"] = current.get("outcome", merged[-1].get("outcome", "pending"))
            continue

        merged.append(current)

    return merged[-3:]


def build_failure_packet(current_step: dict, episodes: list[dict], recent_progress: list[dict]) -> dict:
    return {
        "current_step": deepcopy(current_step or {}),
        "recent_failure_episodes": _merge_failure_episodes(episodes or []),
        "recent_progress_context": deepcopy((recent_progress or [])[-3:]),
    }
