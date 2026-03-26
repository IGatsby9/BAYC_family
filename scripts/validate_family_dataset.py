#!/usr/bin/env python3
"""
Phase 4 — Validate the merged BAYC family dataset.

Checks:
  - Total row count (must be 10,000)
  - All BAYC IDs 0–9999 present exactly once
  - Every MAYC maps to at most one BAYC parent
  - Every BAKC maps to at most one BAYC
  - Serum-type consistency (M1/M2 token IDs match the deterministic formula)
  - M3 token IDs in expected range 30000–30007
  - Distribution stats (1/2/3 MAYCs per BAYC, etc.)
"""
import json
from collections import Counter

from scripts.config import (
    BAYC_TOTAL,
    MAYC_SERUM_MUTATION_RANGE,
    MAYC_MEGA_MUTATION_RANGE,
    mayc_id_from_bayc,
    DATA_DIR,
    setup_logging,
)

log = setup_logging("validate")


def run():
    log.info("═══ Phase 4: Validate Family Dataset ═══")

    path = DATA_DIR / "bayc_family_mapping.json"
    with open(path) as f:
        families = json.load(f)

    report = {
        "total_rows": len(families),
        "checks": [],
        "distribution": {},
        "anomalies": [],
    }

    def check(name: str, passed: bool, detail: str = ""):
        status = "PASS" if passed else "FAIL"
        report["checks"].append({"name": name, "status": status, "detail": detail})
        level = log.info if passed else log.error
        level("  [%s] %s  %s", status, name, detail)

    # ── 1. Row count ─────────────────────────────────────────────────────
    check("row_count_10000", len(families) == BAYC_TOTAL,
          f"Got {len(families)}, expected {BAYC_TOTAL}")

    # ── 2. All BAYC IDs present ──────────────────────────────────────────
    bayc_ids = {r["bayc_id"] for r in families}
    expected_ids = set(range(BAYC_TOTAL))
    missing = expected_ids - bayc_ids
    extra = bayc_ids - expected_ids
    check("all_bayc_ids_present", not missing, f"Missing: {sorted(missing)[:20]}" if missing else "")
    check("no_extra_bayc_ids", not extra, f"Extra: {sorted(extra)[:20]}" if extra else "")

    # ── 3. BAYC ID uniqueness ────────────────────────────────────────────
    id_counts = Counter(r["bayc_id"] for r in families)
    dupes = {k: v for k, v in id_counts.items() if v > 1}
    check("bayc_id_unique", not dupes, f"Duplicates: {dict(list(dupes.items())[:10])}" if dupes else "")

    # ── 4. MAYC uniqueness (each MAYC → at most 1 BAYC) ─────────────────
    mayc_to_bayc: dict[int, list[int]] = {}
    for r in families:
        for field in ("mayc_m1_id", "mayc_m2_id", "mayc_m3_id"):
            mid = r[field]
            if mid is not None:
                mayc_to_bayc.setdefault(mid, []).append(r["bayc_id"])

    mayc_dupes = {k: v for k, v in mayc_to_bayc.items() if len(v) > 1}
    check("mayc_maps_to_one_bayc", not mayc_dupes,
          f"Multi-parent MAYCs: {dict(list(mayc_dupes.items())[:10])}" if mayc_dupes else "")

    # ── 5. BAKC uniqueness ───────────────────────────────────────────────
    bakc_to_bayc: dict[int, list[int]] = {}
    for r in families:
        if r["bakc_id"] is not None:
            bakc_to_bayc.setdefault(r["bakc_id"], []).append(r["bayc_id"])

    bakc_dupes = {k: v for k, v in bakc_to_bayc.items() if len(v) > 1}
    check("bakc_maps_to_one_bayc", not bakc_dupes,
          f"Multi-parent BAKCs: {dict(list(bakc_dupes.items())[:10])}" if bakc_dupes else "")

    # ── 6. BAKC ID == BAYC ID invariant ──────────────────────────────────
    bakc_id_mismatches = [
        r for r in families
        if r["bakc_id"] is not None and r["bakc_id"] != r["bayc_id"]
    ]
    check("bakc_id_equals_bayc_id", not bakc_id_mismatches,
          f"{len(bakc_id_mismatches)} mismatches" if bakc_id_mismatches else "")

    # ── 7. M1/M2 formula consistency ─────────────────────────────────────
    formula_errors = []
    for r in families:
        bayc = r["bayc_id"]
        if r["mayc_m1_id"] is not None:
            expected = mayc_id_from_bayc(bayc, 0)
            if r["mayc_m1_id"] != expected:
                formula_errors.append(f"BAYC#{bayc} M1: got {r['mayc_m1_id']} expected {expected}")
        if r["mayc_m2_id"] is not None:
            expected = mayc_id_from_bayc(bayc, 1)
            if r["mayc_m2_id"] != expected:
                formula_errors.append(f"BAYC#{bayc} M2: got {r['mayc_m2_id']} expected {expected}")

    check("m1_m2_formula_consistent", not formula_errors,
          f"{len(formula_errors)} errors: {formula_errors[:5]}" if formula_errors else "")

    # ── 8. M3 token IDs in expected range ────────────────────────────────
    m3_out_of_range = [
        r for r in families
        if r["mayc_m3_id"] is not None
        and not (MAYC_MEGA_MUTATION_RANGE[0] <= r["mayc_m3_id"] <= MAYC_MEGA_MUTATION_RANGE[1])
    ]
    check("m3_token_ids_in_range", not m3_out_of_range,
          f"{len(m3_out_of_range)} out of range" if m3_out_of_range else "")

    # ── 9. Cross-verify mutation count against MAYC totalSupply ─────────
    total_mutations = sum(1 for r in families for f in ("mayc_m1_id", "mayc_m2_id", "mayc_m3_id") if r[f] is not None)
    # MAYC totalSupply = public sale (10,000) + mutations
    expected_mayc_supply = 10_000 + total_mutations
    try:
        from scripts.rpc import eth_call
        raw = eth_call(
            "0x60E4d786628Fea6478F785A6d7e704777c86a7c6",
            "0x18160ddd"
        )
        actual_mayc_supply = int(raw, 16)
        check("mayc_supply_crosscheck",
              expected_mayc_supply == actual_mayc_supply,
              f"10000 public + {total_mutations} mutations = {expected_mayc_supply}, "
              f"on-chain totalSupply = {actual_mayc_supply}")
    except Exception as exc:
        report["checks"].append({
            "name": "mayc_supply_crosscheck",
            "status": "SKIP",
            "detail": f"Could not reach RPC: {exc}",
        })

    # ── 10. Distribution statistics ──────────────────────────────────────
    mayc_counts = Counter()
    for r in families:
        n = sum(1 for f in ("mayc_m1_id", "mayc_m2_id", "mayc_m3_id") if r[f] is not None)
        mayc_counts[n] += 1

    has_bakc = sum(1 for r in families if r["bakc_id"] is not None)

    report["distribution"] = {
        "bayc_with_0_mayc": mayc_counts[0],
        "bayc_with_1_mayc": mayc_counts[1],
        "bayc_with_2_mayc": mayc_counts[2],
        "bayc_with_3_mayc": mayc_counts[3],
        "bayc_with_bakc": has_bakc,
        "bayc_without_bakc": BAYC_TOTAL - has_bakc,
        "total_m1_mutations": sum(1 for r in families if r["mayc_m1_id"] is not None),
        "total_m2_mutations": sum(1 for r in families if r["mayc_m2_id"] is not None),
        "total_m3_mutations": sum(1 for r in families if r["mayc_m3_id"] is not None),
    }

    log.info("── Distribution ──")
    for k, v in report["distribution"].items():
        log.info("  %s: %d", k, v)

    # ── 11. Anomaly collection ───────────────────────────────────────────
    anomalies = [r for r in families if r["source_confidence"] == "anomaly"]
    report["anomalies"] = anomalies
    if anomalies:
        log.warning("Anomalous records: %d", len(anomalies))
        for a in anomalies[:5]:
            log.warning("  BAYC#%d: %s", a["bayc_id"], a["notes"])

    # ── Overall result ───────────────────────────────────────────────────
    all_passed = all(c["status"] == "PASS" for c in report["checks"])
    report["overall"] = "PASS" if all_passed else "FAIL"
    log.info("═══ Overall: %s ═══", report["overall"])

    out_path = DATA_DIR / "validation_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    log.info("Validation report written → %s", out_path)

    return report


if __name__ == "__main__":
    run()
