#!/usr/bin/env python3
"""
Master orchestrator — runs the full BAYC family mapping pipeline.

  Phase 1: Discover contracts & print extraction plan
  Phase 2a: Backfill BAYC → MAYC mapping
  Phase 2b: Backfill BAYC → BAKC mapping
  Phase 3: Merge into canonical family dataset
  Phase 4: Validate the dataset

Usage:
  python -m scripts.run_pipeline              # full pipeline
  python -m scripts.run_pipeline --skip-fetch  # skip RPC fetching, re-merge/validate only
"""
import argparse
import sys
import time

from scripts.config import setup_logging

log = setup_logging("pipeline")


def main():
    parser = argparse.ArgumentParser(description="BAYC Family Mapping Pipeline")
    parser.add_argument(
        "--skip-fetch", action="store_true",
        help="Skip Phase 1/2 (RPC fetching). Useful to re-merge/validate from cached data.",
    )
    args = parser.parse_args()

    t0 = time.time()

    if not args.skip_fetch:
        # Phase 1
        log.info("▶ Starting Phase 1: Discovery")
        from scripts.discover_contracts_and_events import run as discover
        discover()
        log.info("")

        # Phase 2a
        log.info("▶ Starting Phase 2a: MAYC Backfill")
        from scripts.backfill_bayc_mayc_mapping import run as backfill_mayc
        backfill_mayc()
        log.info("")

        # Phase 2b
        log.info("▶ Starting Phase 2b: BAKC Backfill")
        from scripts.backfill_bayc_bakc_mapping import run as backfill_bakc
        backfill_bakc()
        log.info("")
    else:
        log.info("▶ Skipping Phase 1 & 2 (--skip-fetch)")

    # Phase 3
    log.info("▶ Starting Phase 3: Merge")
    from scripts.merge_family_dataset import run as merge
    merge()
    log.info("")

    # Phase 4
    log.info("▶ Starting Phase 4: Validation")
    from scripts.validate_family_dataset import run as validate
    report = validate()

    elapsed = time.time() - t0
    log.info("")
    log.info("═══ Pipeline complete in %.1f seconds ═══", elapsed)

    if report["overall"] != "PASS":
        log.warning("Validation has failures — check data/validation_report.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
