#!/usr/bin/env python3
"""
Phase 2b — Backfill BAYC → BAKC mapping using Multicall3 batch reads.

Key insight from verified BAKC contract source:
  adoptDog(uint256 baycTokenId) → _safeMint(msg.sender, baycTokenId)
  BAKC token ID IS the BAYC token ID.

We check isMinted(tokenId) for all 10,000 possible BAKC tokens.
"""
import json

from scripts.config import (
    BAKC_ADDRESS,
    BAYC_TOTAL,
    DATA_DIR,
    setup_logging,
)
from scripts.rpc import multicall_tryaggregate, _encode_uint256

log = setup_logging("bakc_backfill")

# isMinted(uint256 tokenId) → bool
IS_MINTED_SIG = "0x33c41a90"


def _encode_is_minted(token_id: int) -> str:
    return IS_MINTED_SIG + _encode_uint256(token_id)


def run():
    log.info("═══ Phase 2b: Backfill BAYC → BAKC Mapping (Multicall3) ═══")

    log.info("Checking BAKC minted status for %d tokens …", BAYC_TOTAL)

    calls = [
        (BAKC_ADDRESS, _encode_is_minted(token_id))
        for token_id in range(BAYC_TOTAL)
    ]
    results = multicall_tryaggregate(calls)

    records: list[dict] = []
    for token_id, (success, data) in enumerate(results):
        if success and len(data) >= 32 and int.from_bytes(data[:32], 'big') == 1:
            records.append({
                "bayc_id": token_id,
                "bakc_id": token_id,
                "method": "MULTICALL_IS_MINTED + IDENTITY_MAPPING",
                "confidence": "confirmed",
                "mint_tx_hash": None,
                "mint_block": None,
                "minted_to": None,
            })

    records.sort(key=lambda r: r["bayc_id"])

    out_path = DATA_DIR / "bayc_bakc_raw.json"
    with open(out_path, "w") as f:
        json.dump(records, f, indent=2)
    log.info("BAKC mapping saved → %s  (%d records)", out_path, len(records))
    log.info("Summary: %d BAYCs have a claimed BAKC dog.", len(records))

    return records


if __name__ == "__main__":
    run()
