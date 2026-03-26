#!/usr/bin/env python3
"""
Phase 2a — Backfill BAYC → MAYC mapping using Multicall3 batch reads.

Strategy:
  M1/M2  Use hasApeBeenMutatedWithType(serumType, apeId) via Multicall3
         for all 10,000 BAYCs × 2 serum types.
         Token IDs derived deterministically from the on-chain formula.

  M3     Use hasApeBeenMutatedWithType(69, apeId) via Multicall3.
         For the ~8 matches, call getMutantIdForApeAndSerumCombination
         to recover the MAYC token ID.
"""
import json

from scripts.config import (
    MAYC_ADDRESS,
    BAYC_TOTAL,
    MEGA_MUTATION_TYPE,
    mayc_id_from_bayc,
    serum_label,
    DATA_DIR,
    setup_logging,
)
from scripts.rpc import multicall_tryaggregate, eth_call, _encode_uint256

log = setup_logging("mayc_backfill")

# hasApeBeenMutatedWithType(uint8 serumType, uint256 apeId) → bool
HAS_MUTATED_SIG = "0xee211233"
# getMutantIdForApeAndSerumCombination(uint256 apeId, uint8 serumTypeId) → uint256
GET_MUTANT_ID_SIG = "0xbd5e5e0c"


def _encode_has_mutated(serum_type: int, ape_id: int) -> str:
    return HAS_MUTATED_SIG + _encode_uint256(serum_type) + _encode_uint256(ape_id)


def _encode_get_mutant_id(ape_id: int, serum_type: int) -> str:
    return GET_MUTANT_ID_SIG + _encode_uint256(ape_id) + _encode_uint256(serum_type)


def run():
    log.info("═══ Phase 2a: Backfill BAYC → MAYC Mapping (Multicall3) ═══")

    bayc_mayc_records: list[dict] = []

    # ── M1 mutations (serumType=0) ───────────────────────────────────────
    log.info("Checking M1 mutations for %d BAYCs …", BAYC_TOTAL)
    m1_calls = [
        (MAYC_ADDRESS, _encode_has_mutated(0, ape_id))
        for ape_id in range(BAYC_TOTAL)
    ]
    m1_results = multicall_tryaggregate(m1_calls)

    m1_count = 0
    for ape_id, (success, data) in enumerate(m1_results):
        if success and len(data) >= 32 and int.from_bytes(data[:32], 'big') == 1:
            m1_count += 1
            bayc_mayc_records.append({
                "bayc_id": ape_id,
                "mayc_id": mayc_id_from_bayc(ape_id, 0),
                "serum_type": 0,
                "serum_label": "M1",
                "method": "MULTICALL_HAS_MUTATED + DETERMINISTIC_FORMULA",
                "confidence": "confirmed",
                "mint_tx_hash": None,
                "mint_block": None,
                "minted_to": None,
            })
    log.info("M1 mutations found: %d", m1_count)

    # ── M2 mutations (serumType=1) ───────────────────────────────────────
    log.info("Checking M2 mutations for %d BAYCs …", BAYC_TOTAL)
    m2_calls = [
        (MAYC_ADDRESS, _encode_has_mutated(1, ape_id))
        for ape_id in range(BAYC_TOTAL)
    ]
    m2_results = multicall_tryaggregate(m2_calls)

    m2_count = 0
    for ape_id, (success, data) in enumerate(m2_results):
        if success and len(data) >= 32 and int.from_bytes(data[:32], 'big') == 1:
            m2_count += 1
            bayc_mayc_records.append({
                "bayc_id": ape_id,
                "mayc_id": mayc_id_from_bayc(ape_id, 1),
                "serum_type": 1,
                "serum_label": "M2",
                "method": "MULTICALL_HAS_MUTATED + DETERMINISTIC_FORMULA",
                "confidence": "confirmed",
                "mint_tx_hash": None,
                "mint_block": None,
                "minted_to": None,
            })
    log.info("M2 mutations found: %d", m2_count)

    # ── M3/MEGA mutations (serumType=69) ─────────────────────────────────
    log.info("Checking M3/MEGA mutations for %d BAYCs …", BAYC_TOTAL)
    m3_calls = [
        (MAYC_ADDRESS, _encode_has_mutated(MEGA_MUTATION_TYPE, ape_id))
        for ape_id in range(BAYC_TOTAL)
    ]
    m3_results = multicall_tryaggregate(m3_calls)

    m3_bayc_ids = []
    for ape_id, (success, data) in enumerate(m3_results):
        if success and len(data) >= 32 and int.from_bytes(data[:32], 'big') == 1:
            m3_bayc_ids.append(ape_id)

    log.info("M3 BAYCs identified: %d → %s", len(m3_bayc_ids), m3_bayc_ids)

    # Fetch exact MAYC token IDs for M3 matches
    for ape_id in m3_bayc_ids:
        calldata = _encode_get_mutant_id(ape_id, MEGA_MUTATION_TYPE)
        try:
            raw = eth_call(MAYC_ADDRESS, calldata)
            mayc_id = int(raw, 16)
            log.info("  BAYC#%d → MAYC#%d (M3)", ape_id, mayc_id)
            bayc_mayc_records.append({
                "bayc_id": ape_id,
                "mayc_id": mayc_id,
                "serum_type": MEGA_MUTATION_TYPE,
                "serum_label": "M3",
                "method": "MULTICALL_HAS_MUTATED + GET_MUTANT_ID",
                "confidence": "confirmed",
                "mint_tx_hash": None,
                "mint_block": None,
                "minted_to": None,
            })
        except Exception as exc:
            log.error("  Failed to get M3 mutant ID for BAYC#%d: %s", ape_id, exc)
            bayc_mayc_records.append({
                "bayc_id": ape_id,
                "mayc_id": None,
                "serum_type": MEGA_MUTATION_TYPE,
                "serum_label": "M3",
                "method": "MULTICALL_FAILED",
                "confidence": "unresolved",
                "mint_tx_hash": None,
                "mint_block": None,
                "minted_to": None,
            })

    # ── Save ─────────────────────────────────────────────────────────────
    bayc_mayc_records.sort(key=lambda r: (r["bayc_id"] or -1, r["serum_type"]))

    out_path = DATA_DIR / "bayc_mayc_raw.json"
    with open(out_path, "w") as f:
        json.dump(bayc_mayc_records, f, indent=2)
    log.info("MAYC mapping saved → %s  (%d records)", out_path, len(bayc_mayc_records))

    log.info("Summary: M1=%d  M2=%d  M3=%d  Total=%d",
             m1_count, m2_count, len(m3_bayc_ids), len(bayc_mayc_records))

    return bayc_mayc_records


if __name__ == "__main__":
    run()
