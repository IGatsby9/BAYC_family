#!/usr/bin/env python3
"""
Generate a compact bayc-family.json for the rillalert app frontend.

Output structure (designed for instant client-side lookups):
{
  "m1": [0, 1, 2, ...],                    // BAYC IDs that have M1 mutations
  "m2": [10, 11, 16, ...],                 // BAYC IDs that have M2 mutations
  "m3": [[8074,30000],[416,30001], ...],    // [bayc_id, mayc_id] pairs
  "noBakc": [4, 6, 12, ...]                // BAYC IDs that do NOT have BAKC (smaller set)
}

The M1/M2 MAYC token IDs are NOT stored — they're derived client-side via:
  M1: bayc_id * 2 + 10000
  M2: bayc_id * 2 + 10001
  BAKC ID always equals BAYC ID when present.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def run():
    with open(DATA_DIR / "bayc_family_mapping.json") as f:
        families = json.load(f)

    m1_baycs = sorted(r["bayc_id"] for r in families if r["mayc_m1_id"] is not None)
    m2_baycs = sorted(r["bayc_id"] for r in families if r["mayc_m2_id"] is not None)
    m3_pairs = sorted(
        [r["bayc_id"], r["mayc_m3_id"]]
        for r in families if r["mayc_m3_id"] is not None
    )
    no_bakc = sorted(r["bayc_id"] for r in families if r["bakc_id"] is None)

    compact = {
        "m1": m1_baycs,
        "m2": m2_baycs,
        "m3": m3_pairs,
        "noBakc": no_bakc,
    }

    out_path = DATA_DIR / "bayc-family.json"
    with open(out_path, "w") as f:
        json.dump(compact, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"Generated {out_path} ({size_kb:.1f} KB)")
    print(f"  M1 BAYCs: {len(m1_baycs)}")
    print(f"  M2 BAYCs: {len(m2_baycs)}")
    print(f"  M3 pairs: {len(m3_pairs)}")
    print(f"  No BAKC:  {len(no_bakc)}")


if __name__ == "__main__":
    run()
