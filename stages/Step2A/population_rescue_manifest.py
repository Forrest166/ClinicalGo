from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


def population_rescue_manifest_path_for_output(output_path: str) -> str:
    path = Path(str(output_path or "").strip())
    stem = path.stem or "output"
    return str(path.with_name(f"{stem}_population_rescue.json"))


@dataclass
class PopulationRescueManifest:
    source_path: str
    output_path: str
    status: str = "pending"
    generated_at: str = ""
    record_ids: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": str(self.source_path or "").strip(),
            "output_path": str(self.output_path or "").strip(),
            "status": str(self.status or "pending").strip() or "pending",
            "generated_at": str(self.generated_at or "").strip(),
            "record_ids": [int(value) for value in self.record_ids],
            "metadata": dict(self.metadata or {}),
        }


def write_population_rescue_manifest(
    *,
    output_path: str,
    source_path: str,
    record_ids: Sequence[int],
    metadata: Mapping[str, Any] | None = None,
) -> str:
    manifest_path = Path(population_rescue_manifest_path_for_output(output_path))
    record_ids = sorted({int(value) for value in record_ids})
    if not record_ids:
        if manifest_path.exists():
            manifest_path.unlink()
        return str(manifest_path)
    payload = PopulationRescueManifest(
        source_path=str(source_path or "").strip(),
        output_path=str(output_path or "").strip(),
        status="pending",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        record_ids=list(record_ids),
        metadata=dict(metadata or {}),
    )
    manifest_path.write_text(json.dumps(payload.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return str(manifest_path)


def read_population_rescue_manifest(manifest_path: str) -> PopulationRescueManifest:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    return PopulationRescueManifest(
        source_path=str(payload.get("source_path", "") or ""),
        output_path=str(payload.get("output_path", "") or ""),
        status=str(payload.get("status", "pending") or "pending"),
        generated_at=str(payload.get("generated_at", "") or ""),
        record_ids=[int(value) for value in payload.get("record_ids", []) or []],
        metadata=dict(payload.get("metadata", {}) or {}),
    )


def update_population_rescue_manifest(
    manifest_path: str,
    *,
    status: str,
    metadata_updates: Mapping[str, Any] | None = None,
) -> PopulationRescueManifest:
    manifest = read_population_rescue_manifest(manifest_path)
    manifest.status = str(status or manifest.status or "pending").strip() or "pending"
    merged = dict(manifest.metadata or {})
    merged.update(dict(metadata_updates or {}))
    manifest.metadata = merged
    Path(manifest_path).write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
