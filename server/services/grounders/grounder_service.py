from __future__ import annotations

from copy import deepcopy
from typing import Any


class GrounderService:
    def __init__(self, uia_backend: Any, vision_backend: Any):
        self._uia_backend = uia_backend
        self._vision_backend = vision_backend

    def locate(self, step: dict, surface_snapshot: dict) -> dict:
        uia_result = self._normalize_result(self._uia_backend.locate(step, surface_snapshot), backend="uia")
        if uia_result["status"] in {"ok", "ambiguous"}:
            return uia_result

        vision_result = self._normalize_result(self._vision_backend.locate(step, surface_snapshot), backend="vision")
        return vision_result

    def observe(self, step: dict, surface_snapshot: dict) -> dict:
        uia_result = self._normalize_result(self._uia_backend.observe(step, surface_snapshot), backend="uia")
        if uia_result["status"] in {"ok", "ambiguous"}:
            return uia_result

        vision_result = self._normalize_result(self._vision_backend.observe(step, surface_snapshot), backend="vision")
        return vision_result

    def _normalize_result(self, result: dict | None, backend: str) -> dict:
        payload = deepcopy(result) if isinstance(result, dict) else {}
        status = payload.get("status") or "not_found"
        normalized = {
            "status": status,
            "backend": backend,
        }

        if status == "ok":
            normalized["targets"] = {
                role: self._annotate_backend(target, backend)
                for role, target in (payload.get("targets") or {}).items()
            }
            return normalized

        if status == "ambiguous":
            normalized["candidate_sets"] = {
                role: [self._annotate_backend(candidate, backend) for candidate in candidates]
                for role, candidates in (payload.get("candidate_sets") or {}).items()
            }
            return normalized

        normalized["targets"] = payload.get("targets") or {}
        if payload.get("candidate_sets"):
            normalized["candidate_sets"] = payload["candidate_sets"]
        return normalized

    def _annotate_backend(self, item: dict, backend: str) -> dict:
        annotated = deepcopy(item) if isinstance(item, dict) else {}
        annotated["backend"] = backend
        return annotated
