# BAYC Family — Canonical on-chain mapping

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Ethereum](https://img.shields.io/badge/chain-Ethereum%20mainnet-627eea.svg)](https://ethereum.org/)

**One row per BAYC (0–9999):** linked **MAYC** tokens (M1 / M2 / M3 serum classes) and **BAKC** dog, built from **Ethereum contract state** — not OpenSea labels, not wallet guesses.

Fork it for your indexer, drop the JSON into an app, or re-run the pipeline to verify.

---

## Why use this?

| You get | Details |
|--------|---------|
| **Complete coverage** | All 10,000 BAYC IDs with nullable MAYC/BAKC fields where applicable |
| **Auditable logic** | Reads Yuga contracts on mainnet; validation cross-checks MAYC `totalSupply()` |
| **Portable outputs** | CSV + JSON under `data/` — plus a tiny **`bayc-family.json`** for UIs |
| **No marketplace API as truth** | Relationships come from chain state and contract rules |

---

## Quick start

### Option A — Use the published dataset only

Download this repo (or clone) and open:

- `data/bayc_family_mapping.csv` — spreadsheet-friendly  
- `data/bayc_family_mapping.json` — one object per BAYC  
- `data/bayc-family.json` — compact lookup for apps (M1/M2 lists + M3 pairs + “no BAKC” IDs)

No Python required.

### Option B — Re-run or verify the pipeline

```bash
git clone https://github.com/IGatsby9/BAYC_family.git
cd BAYC_family

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set ETH_RPC_URL (Alchemy / Infura / any mainnet JSON-RPC)

python -m scripts.run_pipeline
```

Regenerate the compact app JSON after a fresh merge:

```bash
python -m scripts.generate_app_json
```

### Look up any token from the CLI

```bash
python -m scripts.lookup --bayc 42
python -m scripts.lookup --mayc 10084
python -m scripts.lookup --bakc 7777
python -m scripts.lookup 30001        # MAYC M3 — auto-detected
```

---

## What’s in the box

| Artifact | Purpose |
|----------|---------|
| `data/bayc_family_mapping.csv` | Canonical table — **one row per BAYC** |
| `data/bayc_family_mapping.json` | Same data as JSON |
| `data/bayc-family.json` | Small index for frontends (see `scripts/generate_app_json.py`) |
| `data/validation_report.json` | Automated checks + distribution stats |
| `data/extraction_audit_log.json` | Merge-time audit trail |
| `data/extraction_plan.json` | Phase-1 extraction plan |

### Row schema

| Field | Meaning |
|-------|---------|
| `bayc_id` | BAYC token ID `0 … 9999` |
| `bakc_id` | BAKC ID if minted — **same number as BAYC** when present; else `null` |
| `mayc_m1_id` | M1 mutant MAYC ID — `null` if not mutated |
| `mayc_m2_id` | M2 mutant MAYC ID — `null` if not mutated |
| `mayc_m3_id` | M3 / MEGA mutant — `null` if not mutated |
| `all_mayc_ids` | Comma-separated list of all MAYCs for this ape |
| `notes` | Flags e.g. `NO_MAYC`, `NO_BAKC` |
| `source_confidence` | `confirmed` / `anomaly` |

---

## How it works (short)

1. **BAKC ↔ BAYC** — Kennel mints use the **same token ID** as the BAYC. The pipeline uses on-chain `isMinted(tokenId)` (batched via **Multicall3**) across 0–9999.

2. **MAYC M1 / M2** — The contract encodes mutants as  
   `mutantId = apeId × 2 + serumType + 10000` (serum `0` = M1, `1` = M2).  
   Presence is confirmed with `hasApeBeenMutatedWithType` per ape + serum (again via Multicall3). IDs can also be derived mathematically.

3. **MAYC M3 (MEGA)** — Only eight slots (`30000`–`30007`). Parent apes are read with `getMutantIdForApeAndSerumCombination` where needed.

4. **Validation** — Uniqueness rules, formula checks, and a **supply cross-check** against live MAYC `totalSupply()`.

Optional: `scripts/enrich_tx_hashes.py` can attach mint **tx hashes** via `eth_getLogs` (heavier on RPC — not required for the mapping itself).

---

## Contracts (Ethereum mainnet)

| Collection | Address |
|------------|---------|
| BAYC | `0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D` |
| MAYC | `0x60E4d786628Fea6478F785A6d7e704777c86a7c6` |
| BAKC | `0xba30E5F9Bb24caa003E9f2f0497Ad287FDF95623` |
| BACC (serums) | `0x22c36BfdCef207F9c0CC941936eff94D4246d14A` |

---

## Scripts layout

```
scripts/
  run_pipeline.py                   # End-to-end: discover → backfill → merge → validate
  discover_contracts_and_events.py
  backfill_bayc_mayc_mapping.py
  backfill_bayc_bakc_mapping.py
  merge_family_dataset.py
  validate_family_dataset.py
  lookup.py                         # CLI lookup by BAYC / MAYC / BAKC
  generate_app_json.py              # data/bayc-family.json from merged JSON
  enrich_tx_hashes.py               # Optional tx provenance
  config.py                         # Addresses, selectors, formulas
  rpc.py                            # JSON-RPC + Multicall3 batching
```

---

## Validation snapshot

| Check | Result |
|-------|--------|
| Rows | **10,000** (every BAYC ID) |
| MAYC supply cross-check | **PASS** (matches on-chain `totalSupply`) |
| BAKC ID = BAYC ID when present | **PASS** |
| M1 / M2 formula consistency | **PASS** |

**Distribution (high level):** e.g. BAYCs with 0 / 1 / 2 / 3 MAYCs, with / without BAKC — see `data/validation_report.json` for exact counts.

---

## Contributing

Issues and PRs welcome — especially docs, extra validation tests, or ports to other languages. Please keep `.env` out of commits (see `.gitignore`); use `.env.example` only.

---

## License

[MIT](LICENSE) — code and tooling. Dataset is derived from public blockchain data; Yuga Labs owns the underlying NFT IP.

---

<p align="center">
  If this saved you time, consider starring the repo — it helps others find it.
</p>
