#!/usr/bin/env python3
"""
Optional Phase 2c — Enrich the family dataset with mint transaction hashes.

Scans Transfer(from=0x0) events on MAYC and BAKC contracts to capture
the original minting tx hash and block number for each token.

This is an OPTIONAL enrichment step. The family mappings are already
proven by on-chain contract formulas and Multicall3 state reads.
The tx hashes provide additional audit provenance.

NOTE: This requires an RPC that supports eth_getLogs over large ranges.
      Free public RPCs may be too slow or rate-limited for this step.
      Consider using Alchemy/Infura if available.
"""
import json

from scripts.config import (
    MAYC_ADDRESS,
    BAKC_ADDRESS,
    MAYC_DEPLOY_BLOCK,
    BAKC_DEPLOY_BLOCK,
    TRANSFER_EVENT_SIGNATURE,
    ZERO_ADDRESS_TOPIC,
    bayc_id_from_mayc,
    MAYC_SERUM_MUTATION_RANGE,
    MAYC_MEGA_MUTATION_RANGE,
    DATA_DIR,
    setup_logging,
)
from scripts.rpc import scan_logs, parse_transfer_log, get_block_number

log = setup_logging("enrich")


def run():
    log.info("═══ Phase 2c: Enrich with Mint Transaction Hashes ═══")
    log.info("NOTE: This step requires an RPC with good eth_getLogs support.")
    log.info("Consider using Alchemy or Infura if on a free public RPC.")

    latest_block = get_block_number()

    # ── Load existing raw data ───────────────────────────────────────────
    with open(DATA_DIR / "bayc_mayc_raw.json") as f:
        mayc_records = json.load(f)
    with open(DATA_DIR / "bayc_bakc_raw.json") as f:
        bakc_records = json.load(f)

    # ── Scan MAYC mint events ────────────────────────────────────────────
    log.info("Scanning MAYC mint events (this may take a while) …")
    try:
        mayc_mint_logs = scan_logs(
            address=MAYC_ADDRESS,
            topics=[TRANSFER_EVENT_SIGNATURE, ZERO_ADDRESS_TOPIC],
            start_block=MAYC_DEPLOY_BLOCK,
            end_block=latest_block,
        )
        mayc_mints = {
            parse_transfer_log(l)["token_id"]: parse_transfer_log(l)
            for l in mayc_mint_logs
        }
        log.info("MAYC mints fetched: %d", len(mayc_mints))

        enriched_mayc = 0
        for rec in mayc_records:
            mint = mayc_mints.get(rec["mayc_id"])
            if mint:
                rec["mint_tx_hash"] = mint["tx_hash"]
                rec["mint_block"] = mint["block_number"]
                rec["minted_to"] = mint["to"]
                enriched_mayc += 1
        log.info("MAYC records enriched with tx hashes: %d / %d", enriched_mayc, len(mayc_records))

    except Exception as exc:
        log.warning("MAYC event scan failed: %s. Skipping MAYC enrichment.", exc)

    # ── Scan BAKC mint events ────────────────────────────────────────────
    log.info("Scanning BAKC mint events …")
    try:
        bakc_mint_logs = scan_logs(
            address=BAKC_ADDRESS,
            topics=[TRANSFER_EVENT_SIGNATURE, ZERO_ADDRESS_TOPIC],
            start_block=BAKC_DEPLOY_BLOCK,
            end_block=latest_block,
        )
        bakc_mints = {
            parse_transfer_log(l)["token_id"]: parse_transfer_log(l)
            for l in bakc_mint_logs
        }
        log.info("BAKC mints fetched: %d", len(bakc_mints))

        enriched_bakc = 0
        for rec in bakc_records:
            mint = bakc_mints.get(rec["bakc_id"])
            if mint:
                rec["mint_tx_hash"] = mint["tx_hash"]
                rec["mint_block"] = mint["block_number"]
                rec["minted_to"] = mint["to"]
                enriched_bakc += 1
        log.info("BAKC records enriched with tx hashes: %d / %d", enriched_bakc, len(bakc_records))

    except Exception as exc:
        log.warning("BAKC event scan failed: %s. Skipping BAKC enrichment.", exc)

    # ── Save enriched data ───────────────────────────────────────────────
    with open(DATA_DIR / "bayc_mayc_raw.json", "w") as f:
        json.dump(mayc_records, f, indent=2)
    with open(DATA_DIR / "bayc_bakc_raw.json", "w") as f:
        json.dump(bakc_records, f, indent=2)

    log.info("Enriched data saved. Run --skip-fetch to re-merge & validate.")
    log.info("  python -m scripts.run_pipeline --skip-fetch")


if __name__ == "__main__":
    run()
