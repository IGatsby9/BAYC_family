#!/usr/bin/env python3
"""
Phase 1 — Contract Discovery & Extraction Plan

Connects to the Ethereum RPC, verifies contract accessibility, fetches
collection sizes, and prints the deterministic extraction strategy derived
from on-chain contract source analysis.
"""
import json
from scripts.config import (
    BAYC_ADDRESS, MAYC_ADDRESS, BAKC_ADDRESS, BACC_ADDRESS,
    BAYC_TOTAL, SERUM_MUTATION_OFFSET, NUM_MUTANT_TYPES,
    MAYC_SERUM_MUTATION_RANGE, MAYC_MEGA_MUTATION_RANGE,
    MAYC_PUBLIC_SALE_RANGE, mayc_id_from_bayc, bayc_id_from_mayc,
    DATA_DIR, setup_logging,
)
from scripts.rpc import rpc_call, get_block_number

log = setup_logging("discover")


def _total_supply(address: str) -> int:
    sig = "0x18160ddd"  # totalSupply()
    raw = rpc_call("eth_call", [{"to": address, "data": sig}, "latest"])
    return int(raw, 16)


def run():
    log.info("═══ Phase 1: Contract Discovery & Extraction Plan ═══")

    # ── 1. RPC connectivity ──────────────────────────────────────────────
    latest = get_block_number()
    log.info("Connected to Ethereum RPC — latest block: %s", f"{latest:,}")

    # ── 2. Collection sizes ──────────────────────────────────────────────
    bayc_supply = _total_supply(BAYC_ADDRESS)
    mayc_supply = _total_supply(MAYC_ADDRESS)
    bakc_supply = _total_supply(BAKC_ADDRESS)

    log.info("BAYC  %s  totalSupply = %d", BAYC_ADDRESS, bayc_supply)
    log.info("MAYC  %s  totalSupply = %d", MAYC_ADDRESS, mayc_supply)
    log.info("BAKC  %s  totalSupply = %d", BAKC_ADDRESS, bakc_supply)
    log.info("BACC  %s  (serum contract)", BACC_ADDRESS)

    # ── 3. Formula verification ──────────────────────────────────────────
    # Spot-check the deterministic formula against known constants
    assert mayc_id_from_bayc(0, 0) == 10000,  "Formula check failed: BAYC#0 M1"
    assert mayc_id_from_bayc(0, 1) == 10001,  "Formula check failed: BAYC#0 M2"
    assert mayc_id_from_bayc(9999, 0) == 29998, "Formula check failed: BAYC#9999 M1"
    assert mayc_id_from_bayc(9999, 1) == 29999, "Formula check failed: BAYC#9999 M2"
    assert bayc_id_from_mayc(10000) == (0, 0),   "Reverse check failed"
    assert bayc_id_from_mayc(10001) == (0, 1),   "Reverse check failed"
    assert bayc_id_from_mayc(29999) == (9999, 1), "Reverse check failed"
    log.info("Deterministic M1/M2 formula verified ✓")

    # ── 4. Print the extraction plan ─────────────────────────────────────
    plan = {
        "extraction_plan": {
            "bayc_to_mayc_m1_m2": {
                "method": "DETERMINISTIC_FORMULA",
                "description": (
                    "MAYC contract getMutantId(serumType, apeId) = "
                    "(apeId * 2) + serumType + 10000. "
                    "Scan Transfer(from=0x0) events on MAYC in token-ID range "
                    f"[{MAYC_SERUM_MUTATION_RANGE[0]}, {MAYC_SERUM_MUTATION_RANGE[1]}]. "
                    "Reverse formula gives BAYC parent + serum type."
                ),
                "source_of_truth": "on-chain ERC-721 Transfer event + verified contract formula",
                "confidence": "CONFIRMED",
            },
            "bayc_to_mayc_m3": {
                "method": "TRANSACTION_INPUT_DECODE",
                "description": (
                    "Only 8 MEGA mutant tokens (IDs 30000-30007) exist. "
                    "Scan Transfer(from=0x0) on MAYC in that range, then decode "
                    "the mutateApeWithSerum(uint256,uint256) tx input to extract apeId."
                ),
                "source_of_truth": "on-chain tx input calldata + Transfer event",
                "confidence": "CONFIRMED",
                "max_tokens": 8,
            },
            "bayc_to_bakc": {
                "method": "IDENTITY_MAPPING",
                "description": (
                    "BAKC adoptDog(uint256 baycTokenId) calls _safeMint(msg.sender, baycTokenId). "
                    "BAKC token ID IS the BAYC token ID. Scan Transfer(from=0x0) on BAKC "
                    "to get the set of minted BAKC IDs."
                ),
                "source_of_truth": "on-chain verified contract source + Transfer event",
                "confidence": "CONFIRMED",
            },
        },
        "contracts": {
            "BAYC": {"address": BAYC_ADDRESS, "supply": bayc_supply},
            "MAYC": {"address": MAYC_ADDRESS, "supply": mayc_supply},
            "BAKC": {"address": BAKC_ADDRESS, "supply": bakc_supply},
            "BACC_SERUMS": {"address": BACC_ADDRESS, "role": "Serum ERC-1155 (burned on mutation)"},
        },
        "token_id_ranges": {
            "BAYC": "0–9999",
            "MAYC_public_sale": f"{MAYC_PUBLIC_SALE_RANGE[0]}–{MAYC_PUBLIC_SALE_RANGE[1]} (no BAYC parent)",
            "MAYC_M1_M2": f"{MAYC_SERUM_MUTATION_RANGE[0]}–{MAYC_SERUM_MUTATION_RANGE[1]}",
            "MAYC_M3_MEGA": f"{MAYC_MEGA_MUTATION_RANGE[0]}–{MAYC_MEGA_MUTATION_RANGE[1]}",
            "BAKC": "0–9999 (== BAYC token ID)",
        },
        "formulas": {
            "M1_mutant_id": "bayc_id * 2 + 0 + 10000",
            "M2_mutant_id": "bayc_id * 2 + 1 + 10000",
            "reverse_bayc_id": "(mayc_id - 10000) // 2",
            "reverse_serum": "(mayc_id - 10000) % 2   → 0=M1, 1=M2",
        },
        "events_used": [
            "Transfer(address indexed from, address indexed to, uint256 indexed tokenId) — 0xddf252ad…",
        ],
        "potential_failure_modes": [
            "RPC rate limits on eth_getLogs — mitigated by adaptive chunking",
            "M3 MEGA mutations require tx input decode — only 8 txs, trivially handled",
            "BAKC adoptNDogs() batch minting — still uses same token-ID = BAYC-ID rule",
            "Public-sale MAYC (0-9999) have NO BAYC parent — must not be confused with mutations",
        ],
    }

    out_path = DATA_DIR / "extraction_plan.json"
    with open(out_path, "w") as f:
        json.dump(plan, f, indent=2)
    log.info("Extraction plan written → %s", out_path)

    print("\n" + json.dumps(plan, indent=2))
    return plan


if __name__ == "__main__":
    run()
