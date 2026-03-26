#!/usr/bin/env python3
"""
Phase 3 — Merge MAYC + BAKC intermediate data into a canonical family dataset.

Produces one row per BAYC token (0–9999) with columns:
  bayc_id, bakc_id, mayc_m1_id, mayc_m2_id, mayc_m3_id, all_mayc_ids,
  notes, source_confidence, provenance
"""
import csv
import json
from collections import defaultdict

from scripts.config import BAYC_TOTAL, DATA_DIR, setup_logging

log = setup_logging("merge")


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def run():
    log.info("═══ Phase 3: Merge Family Dataset ═══")

    # ── Load intermediate data ───────────────────────────────────────────
    mayc_raw_path = DATA_DIR / "bayc_mayc_raw.json"
    bakc_raw_path = DATA_DIR / "bayc_bakc_raw.json"

    mayc_records = _load_json(mayc_raw_path)
    bakc_records = _load_json(bakc_raw_path)
    log.info("Loaded %d MAYC records, %d BAKC records", len(mayc_records), len(bakc_records))

    # ── Index MAYC records by BAYC ID and serum label ────────────────────
    mayc_by_bayc: dict[int, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in mayc_records:
        if r["bayc_id"] is not None:
            mayc_by_bayc[r["bayc_id"]][r["serum_label"]].append(r)

    # ── Index BAKC records by BAYC ID ────────────────────────────────────
    bakc_by_bayc: dict[int, dict] = {}
    for r in bakc_records:
        bakc_by_bayc[r["bayc_id"]] = r

    # ── Build canonical family rows ──────────────────────────────────────
    families: list[dict] = []
    audit_rows: list[dict] = []

    for bayc_id in range(BAYC_TOTAL):
        row = {
            "bayc_id": bayc_id,
            "bakc_id": None,
            "mayc_m1_id": None,
            "mayc_m2_id": None,
            "mayc_m3_id": None,
            "all_mayc_ids": [],
            "notes": [],
            "source_confidence": "confirmed",
        }

        # BAKC
        if bayc_id in bakc_by_bayc:
            br = bakc_by_bayc[bayc_id]
            row["bakc_id"] = br["bakc_id"]
            audit_rows.append({
                "bayc_id": bayc_id,
                "relation": "BAKC",
                "related_id": br["bakc_id"],
                "method": br["method"],
                "tx_hash": br["mint_tx_hash"],
                "block": br["mint_block"],
            })

        # MAYC
        mayc_data = mayc_by_bayc.get(bayc_id, {})

        for label, field in [("M1", "mayc_m1_id"), ("M2", "mayc_m2_id"), ("M3", "mayc_m3_id")]:
            entries = mayc_data.get(label, [])
            if len(entries) == 1:
                row[field] = entries[0]["mayc_id"]
                row["all_mayc_ids"].append(entries[0]["mayc_id"])
                audit_rows.append({
                    "bayc_id": bayc_id,
                    "relation": f"MAYC_{label}",
                    "related_id": entries[0]["mayc_id"],
                    "method": entries[0]["method"],
                    "tx_hash": entries[0]["mint_tx_hash"],
                    "block": entries[0]["mint_block"],
                })
            elif len(entries) > 1:
                row["notes"].append(f"DUPLICATE_{label}_MUTATION")
                row["source_confidence"] = "anomaly"
                row[field] = entries[0]["mayc_id"]
                for e in entries:
                    row["all_mayc_ids"].append(e["mayc_id"])

        if not row["all_mayc_ids"]:
            row["notes"].append("NO_MAYC")
        if row["bakc_id"] is None:
            row["notes"].append("NO_BAKC")

        row["notes"] = "; ".join(row["notes"]) if row["notes"] else ""
        row["all_mayc_ids"] = ",".join(str(x) for x in sorted(row["all_mayc_ids"])) if row["all_mayc_ids"] else ""

        families.append(row)

    # ── Export CSV ────────────────────────────────────────────────────────
    csv_path = DATA_DIR / "bayc_family_mapping.csv"
    fieldnames = [
        "bayc_id", "bakc_id", "mayc_m1_id", "mayc_m2_id", "mayc_m3_id",
        "all_mayc_ids", "notes", "source_confidence",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(families)
    log.info("CSV written → %s", csv_path)

    # ── Export JSON ───────────────────────────────────────────────────────
    json_path = DATA_DIR / "bayc_family_mapping.json"
    with open(json_path, "w") as f:
        json.dump(families, f, indent=2)
    log.info("JSON written → %s", json_path)

    # ── Export audit log ─────────────────────────────────────────────────
    audit_path = DATA_DIR / "extraction_audit_log.json"
    with open(audit_path, "w") as f:
        json.dump(audit_rows, f, indent=2)
    log.info("Audit log written → %s  (%d entries)", audit_path, len(audit_rows))

    # ── Quick stats ──────────────────────────────────────────────────────
    has_m1 = sum(1 for r in families if r["mayc_m1_id"] is not None)
    has_m2 = sum(1 for r in families if r["mayc_m2_id"] is not None)
    has_m3 = sum(1 for r in families if r["mayc_m3_id"] is not None)
    has_bakc = sum(1 for r in families if r["bakc_id"] is not None)
    has_any_mayc = sum(1 for r in families if r["all_mayc_ids"])

    log.info("── Merge Stats ──")
    log.info("  Total BAYC rows:     %d", len(families))
    log.info("  With M1 MAYC:        %d", has_m1)
    log.info("  With M2 MAYC:        %d", has_m2)
    log.info("  With M3 MAYC:        %d", has_m3)
    log.info("  With any MAYC:       %d", has_any_mayc)
    log.info("  With BAKC:           %d", has_bakc)
    log.info("  No MAYC at all:      %d", BAYC_TOTAL - has_any_mayc)
    log.info("  No BAKC:             %d", BAYC_TOTAL - has_bakc)

    return families


if __name__ == "__main__":
    run()
