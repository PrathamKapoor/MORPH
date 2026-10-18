"""Reproducible research benchmark export in JSON and CSV formats."""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from morph.common.security import sanitize_export_path


def export_benchmark_json(
    report_data: dict[str, Any],
    export_dir: str | Path | None = None,
) -> Path:
    """Export benchmark evaluation results as a standardized, checksummed JSON file."""
    if export_dir is None:
        root = Path(__file__).resolve().parents[3]
        export_dir = root / "exports"
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = sanitize_export_path(export_dir, f"benchmark_report_{timestamp_str}.json")

    payload = {
        "export_metadata": {
            "system": "MORPH 2.0",
            "exported_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "author": "Pratham Kapoor <prathamkapoor027@gmail.com>",
            "schema_version": "morph-benchmark-v1.0",
        },
        "results": report_data,
    }

    raw_json = json.dumps(payload, indent=2)
    sha256 = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
    payload["export_metadata"]["sha256_checksum"] = sha256

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return out_path


def export_benchmark_csv(
    report_data: dict[str, Any],
    export_dir: str | Path | None = None,
) -> Path:
    """Export summary metrics table as CSV."""
    if export_dir is None:
        root = Path(__file__).resolve().parents[3]
        export_dir = root / "exports"
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = sanitize_export_path(export_dir, f"benchmark_summary_{timestamp_str}.csv")

    fieldnames = [
        "Condition",
        "Unintended_Dispatches",
        "Non_Command_Hours",
        "FA_Per_Hour",
        "Recall",
        "Precision",
        "Latency_P50_ms",
        "Latency_P95_ms",
    ]

    rows = []
    for cond_key, label in [
        ("condition_a", "A_Fixed_Thresholds"),
        ("condition_b", "B_Personalized_Prototype"),
        ("condition_c", "C_MORPH_Intention_Gated"),
    ]:
        c = report_data.get(cond_key, {})
        fa_hr = c.get("false_activations_per_hour")
        rec = c.get("recall")
        prec = c.get("precision")
        p50 = c.get("latency_p50_ms")
        p95 = c.get("latency_p95_ms")

        rows.append(
            {
                "Condition": label,
                "Unintended_Dispatches": c.get("unintended_dispatches", 0),
                "Non_Command_Hours": f"{c.get('non_command_hours', 0.0):.4f}",
                "FA_Per_Hour": "N/A" if fa_hr is None else f"{fa_hr:.2f}",
                "Recall": "N/A" if rec is None else f"{rec:.4f}",
                "Precision": "N/A" if prec is None else f"{prec:.4f}",
                "Latency_P50_ms": "N/A" if p50 is None else f"{p50:.1f}",
                "Latency_P95_ms": "N/A" if p95 is None else f"{p95:.1f}",
            }
        )

    # Include ablations if present
    ablations = report_data.get("ablations", {})
    for abl_key, label in [
        ("no_hold", "Ablation_C_No_Hold"),
        ("no_release", "Ablation_C_No_Release"),
        ("no_margin", "Ablation_C_No_Margin"),
    ]:
        if abl_key in ablations:
            c = ablations[abl_key]
            fa_hr = c.get("false_activations_per_hour")
            rec = c.get("recall")
            prec = c.get("precision")
            p50 = c.get("latency_p50_ms")
            p95 = c.get("latency_p95_ms")
            rows.append(
                {
                    "Condition": label,
                    "Unintended_Dispatches": c.get("unintended_dispatches", 0),
                    "Non_Command_Hours": f"{c.get('non_command_hours', 0.0):.4f}",
                    "FA_Per_Hour": "N/A" if fa_hr is None else f"{fa_hr:.2f}",
                    "Recall": "N/A" if rec is None else f"{rec:.4f}",
                    "Precision": "N/A" if prec is None else f"{prec:.4f}",
                    "Latency_P50_ms": "N/A" if p50 is None else f"{p50:.1f}",
                    "Latency_P95_ms": "N/A" if p95 is None else f"{p95:.1f}",
                }
            )

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return out_path
