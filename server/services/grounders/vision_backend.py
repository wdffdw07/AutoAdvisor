from __future__ import annotations


class VisionBackend:
    def locate(self, step: dict, surface_snapshot: dict) -> dict:
        return {"status": "not_found", "targets": {}}

    def observe(self, step: dict, surface_snapshot: dict) -> dict:
        return {"status": "not_found", "targets": {}}
