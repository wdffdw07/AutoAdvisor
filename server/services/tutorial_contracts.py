from __future__ import annotations

from copy import deepcopy

ALLOWED_TARGET_KINDS = {"single", "multiple", "source_target", "region_only"}
ALLOWED_SUCCESS_TYPES = {
    "window_changed",
    "element_appeared",
    "element_disappeared",
    "element_state_changed",
    "text_changed",
    "selection_changed",
    "region_changed",
    "user_confirmed",
}

REQUIRED_STEP_FIELDS = ("id", "title", "instruction", "target", "success_criteria", "window_expectation")


def _raise_missing(field_name: str) -> None:
    raise ValueError(f"step missing required field: {field_name}")


def _validate_target(target: dict) -> dict:
    if not isinstance(target, dict):
        raise ValueError("target must be a dictionary")

    kind = target.get("kind")
    if kind not in ALLOWED_TARGET_KINDS:
        raise ValueError("target.kind must be one of the supported visual target kinds")

    normalized = deepcopy(target)

    if kind in {"single", "multiple", "region_only"}:
        hints = normalized.get("hints")
        if not isinstance(hints, dict):
            raise ValueError("target.hints must be a dictionary")
    elif kind == "source_target":
        source = normalized.get("source")
        destination = normalized.get("destination")
        if not isinstance(source, dict) or not isinstance(destination, dict):
            raise ValueError("source_target targets require source and destination dictionaries")

    return normalized


def _validate_success_criteria(criteria: list[dict]) -> list[dict]:
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("success_criteria must be a non-empty list")

    normalized = []
    for item in criteria:
        if not isinstance(item, dict):
            raise ValueError("success_criteria entries must be dictionaries")
        criterion_type = item.get("type")
        if criterion_type not in ALLOWED_SUCCESS_TYPES:
            raise ValueError("success_criteria contains an unsupported type")
        normalized.append(deepcopy(item))

    return normalized


def is_visualizable_step(step: dict) -> bool:
    target = step.get("target")
    if not isinstance(target, dict):
        return False

    kind = target.get("kind")
    if kind not in ALLOWED_TARGET_KINDS:
        return False

    if kind in {"single", "multiple", "region_only"}:
        hints = target.get("hints")
        return isinstance(hints, dict) and bool(hints)

    source = target.get("source")
    destination = target.get("destination")
    return isinstance(source, dict) and isinstance(destination, dict) and bool(source) and bool(destination)


def validate_step(step: dict) -> dict:
    if not isinstance(step, dict):
        raise ValueError("step must be a dictionary")

    for field_name in REQUIRED_STEP_FIELDS:
        if field_name not in step:
            _raise_missing(field_name)

    normalized = deepcopy(step)
    normalized["critical"] = bool(normalized.get("critical", False))
    normalized["recovery_hints"] = deepcopy(normalized.get("recovery_hints") or {})

    if not isinstance(normalized["window_expectation"], dict) or not normalized["window_expectation"]:
        raise ValueError("window_expectation must be a non-empty dictionary")

    normalized["target"] = _validate_target(normalized["target"])
    normalized["success_criteria"] = _validate_success_criteria(normalized["success_criteria"])

    if not is_visualizable_step(normalized):
        raise ValueError("step must remain visualizable by the grounding layer")

    return normalized


def validate_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("plan must be a dictionary")

    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("plan.steps must be a non-empty list")

    normalized = deepcopy(plan)
    normalized["goal"] = str(normalized.get("goal") or "")
    normalized["steps"] = [validate_step(step) for step in steps]
    return normalized
