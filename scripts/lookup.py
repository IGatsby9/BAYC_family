#!/usr/bin/env python3
"""
Interactive family lookup — search by any BAYC, MAYC, or BAKC token ID.

Usage:
  python -m scripts.lookup 1234                 # auto-detect
  python -m scripts.lookup --bayc 42
  python -m scripts.lookup --mayc 10084
  python -m scripts.lookup --bakc 7777
"""
import argparse
import json
import sys

from scripts.config import (
    BAYC_TOTAL,
    MAYC_SERUM_MUTATION_RANGE,
    MAYC_MEGA_MUTATION_RANGE,
    MAYC_PUBLIC_SALE_RANGE,
    DATA_DIR,
)


def _load_dataset() -> list[dict]:
    path = DATA_DIR / "bayc_family_mapping.json"
    if not path.exists():
        print(f"ERROR: Dataset not found at {path}. Run the pipeline first.")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def _load_audit() -> dict:
    path = DATA_DIR / "extraction_audit_log.json"
    if not path.exists():
        return {}
    with open(path) as f:
        rows = json.load(f)
    index: dict[tuple, list[dict]] = {}
    for r in rows:
        key = r["bayc_id"]
        index.setdefault(key, []).append(r)
    return index


def _build_indices(families: list[dict]):
    by_bayc = {}
    by_mayc = {}
    by_bakc = {}
    for row in families:
        by_bayc[row["bayc_id"]] = row
        for field in ("mayc_m1_id", "mayc_m2_id", "mayc_m3_id"):
            if row[field] is not None:
                by_mayc[row[field]] = row
        if row["bakc_id"] is not None:
            by_bakc[row["bakc_id"]] = row
    return by_bayc, by_mayc, by_bakc


def _fmt(row: dict, audit: dict) -> str:
    lines = [
        f"╔═══════════════════════════════════════════════╗",
        f"║  BAYC Family — Ape #{row['bayc_id']:<5}                    ║",
        f"╠═══════════════════════════════════════════════╣",
    ]

    # BAKC
    bakc = row["bakc_id"]
    lines.append(f"║  BAKC Dog:   {'#' + str(bakc) if bakc is not None else '—  (not claimed)':>30} ║")

    # MAYC
    for label, field in [("M1", "mayc_m1_id"), ("M2", "mayc_m2_id"), ("M3", "mayc_m3_id")]:
        mid = row[field]
        lines.append(f"║  MAYC {label}:    {'#' + str(mid) if mid is not None else '—  (not mutated)':>30} ║")

    # Notes
    if row["notes"]:
        lines.append(f"║  Notes:      {row['notes'][:30]:>30} ║")
    lines.append(f"║  Confidence: {row['source_confidence']:>30} ║")

    # Audit trail
    audit_entries = audit.get(row["bayc_id"], [])
    if audit_entries:
        lines.append(f"╠═══════════════════════════════════════════════╣")
        lines.append(f"║  Provenance                                   ║")
        for a in audit_entries:
            method = a.get("method", "")[:22]
            block_str = str(a.get("block") or "—")
            tx_h = a.get("tx_hash")
            tx_short = tx_h[:16] + "…" if tx_h else "formula-derived"
            lines.append(f"║  {a['relation']:>8}  {tx_short:<18} {method} ║")

    lines.append(f"╚═══════════════════════════════════════════════╝")
    return "\n".join(lines)


def _detect_id_type(token_id: int) -> str:
    """Heuristic: determine whether an ID is likely BAYC, MAYC, or BAKC."""
    if MAYC_SERUM_MUTATION_RANGE[0] <= token_id <= MAYC_SERUM_MUTATION_RANGE[1]:
        return "mayc"
    if MAYC_MEGA_MUTATION_RANGE[0] <= token_id <= MAYC_MEGA_MUTATION_RANGE[1]:
        return "mayc"
    if MAYC_PUBLIC_SALE_RANGE[0] <= token_id <= MAYC_PUBLIC_SALE_RANGE[1]:
        return "ambiguous"  # could be BAYC, BAKC, or public-sale MAYC
    return "bayc_or_bakc"


def main():
    parser = argparse.ArgumentParser(description="BAYC Family Lookup")
    parser.add_argument("token_id", type=int, nargs="?", help="Token ID to search (auto-detects collection)")
    parser.add_argument("--bayc", type=int, help="Lookup by BAYC token ID")
    parser.add_argument("--mayc", type=int, help="Lookup by MAYC token ID")
    parser.add_argument("--bakc", type=int, help="Lookup by BAKC token ID")
    args = parser.parse_args()

    families = _load_dataset()
    audit = _load_audit()
    by_bayc, by_mayc, by_bakc = _build_indices(families)

    results = []

    if args.bayc is not None:
        row = by_bayc.get(args.bayc)
        if row:
            results.append(row)
        else:
            print(f"No BAYC #{args.bayc} found in dataset.")

    elif args.mayc is not None:
        row = by_mayc.get(args.mayc)
        if row:
            results.append(row)
        elif MAYC_PUBLIC_SALE_RANGE[0] <= args.mayc <= MAYC_PUBLIC_SALE_RANGE[1]:
            print(f"MAYC #{args.mayc} is a public-sale mutant — it has NO BAYC parent.")
        else:
            print(f"No family found for MAYC #{args.mayc}.")

    elif args.bakc is not None:
        row = by_bakc.get(args.bakc)
        if row:
            results.append(row)
        else:
            print(f"No family found for BAKC #{args.bakc}. It may not have been claimed.")

    elif args.token_id is not None:
        tid = args.token_id
        id_type = _detect_id_type(tid)

        if id_type == "mayc":
            row = by_mayc.get(tid)
            if row:
                print(f"(Detected as MAYC token ID)")
                results.append(row)
            else:
                print(f"No family found for MAYC #{tid}.")

        elif id_type == "ambiguous":
            print(f"Token ID {tid} is in the 0–9999 range, which is shared by BAYC, BAKC, and public-sale MAYC.")
            print(f"Showing BAYC #{tid} family:\n")
            row = by_bayc.get(tid)
            if row:
                results.append(row)
            else:
                print(f"No BAYC #{tid} found.")

        else:  # bayc_or_bakc
            row = by_bayc.get(tid) or by_bakc.get(tid)
            if row:
                results.append(row)
            else:
                print(f"No family found for token ID {tid}.")
    else:
        parser.print_help()
        return

    for row in results:
        print(_fmt(row, audit))


if __name__ == "__main__":
    main()
