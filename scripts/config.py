"""
Central configuration for BAYC family mapping pipeline.
All contract addresses, ABIs, constants, and derivation formulas live here.
"""
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── RPC ──────────────────────────────────────────────────────────────────────
ETH_RPC_URL = os.getenv("ETH_RPC_URL", "https://eth.llamarpc.com")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")

# ── Contract Addresses ───────────────────────────────────────────────────────
BAYC_ADDRESS = "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D"
MAYC_ADDRESS = "0x60E4d786628Fea6478F785A6d7e704777c86a7c6"
BAKC_ADDRESS = "0xba30E5F9Bb24caa003E9f2f0497Ad287FDF95623"
BACC_ADDRESS = "0x22c36BfdCef207F9c0CC941936eff94D4246d14A"  # Bored Ape Chemistry Club (serums)

# ── Deployment Blocks (approximate, used as scan start) ──────────────────────
BAYC_DEPLOY_BLOCK = 12_287_507   # April 22, 2021
BAKC_DEPLOY_BLOCK = 12_643_798   # June 18, 2021
MAYC_DEPLOY_BLOCK = 13_108_863   # August 28, 2021

# ── MAYC Token ID Ranges & Formula Constants ─────────────────────────────────
# Source: MutantApeYachtClub.sol verified on Etherscan
NUM_MUTANT_TYPES = 2
MEGA_MUTATION_TYPE = 69
SERUM_MUTATION_OFFSET = 10_000
PS_MAX_MUTANTS = 10_000         # public-sale minted mutants (IDs 0-9999)
NUM_MEGA_MUTANTS = 8            # IDs 30000-30007
MAX_MEGA_MUTATION_ID = 30_007

MAYC_PUBLIC_SALE_RANGE = (0, 9_999)
MAYC_SERUM_MUTATION_RANGE = (10_000, 29_999)
MAYC_MEGA_MUTATION_RANGE = (30_000, 30_007)

BAYC_TOKEN_RANGE = (0, 9_999)
BAYC_TOTAL = 10_000

# ── Deterministic MAYC ID Formulas ───────────────────────────────────────────

def mayc_id_from_bayc(bayc_id: int, serum_type: int) -> int:
    """
    Replicate the on-chain getMutantId formula for M1/M2 serums.
    getMutantId(serumType, apeId) = (apeId * NUM_MUTANT_TYPES) + serumType + SERUM_MUTATION_OFFSET
    """
    assert serum_type in (0, 1), "Only M1 (0) and M2 (1) use the deterministic formula"
    return (bayc_id * NUM_MUTANT_TYPES) + serum_type + SERUM_MUTATION_OFFSET


def bayc_id_from_mayc(mayc_id: int) -> tuple[int, int]:
    """
    Reverse the on-chain formula for M1/M2 MAYC token IDs.
    Returns (bayc_id, serum_type) where serum_type 0=M1, 1=M2.
    Only valid for MAYC IDs in the serum-mutation range [10000, 29999].
    """
    assert MAYC_SERUM_MUTATION_RANGE[0] <= mayc_id <= MAYC_SERUM_MUTATION_RANGE[1]
    offset = mayc_id - SERUM_MUTATION_OFFSET
    bayc_id = offset // NUM_MUTANT_TYPES
    serum_type = offset % NUM_MUTANT_TYPES
    return bayc_id, serum_type


def serum_label(serum_type: int) -> str:
    return {0: "M1", 1: "M2", 69: "M3"}.get(serum_type, f"UNKNOWN({serum_type})")


# ── ERC-721 Transfer Event ───────────────────────────────────────────────────
TRANSFER_EVENT_SIGNATURE = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ZERO_ADDRESS_TOPIC = "0x" + "0" * 64

# ── Minimal ABIs ─────────────────────────────────────────────────────────────
ERC721_ENUMERABLE_ABI = json.loads("""[
  {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]""")

MAYC_ABI_FRAGMENT = json.loads("""[
  {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"apeId","type":"uint256"},{"internalType":"uint8","name":"serumTypeId","type":"uint8"}],"name":"getMutantIdForApeAndSerumCombination","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint8","name":"serumType","type":"uint8"},{"internalType":"uint256","name":"apeId","type":"uint256"}],"name":"hasApeBeenMutatedWithType","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},
  {"inputs":[],"name":"numMutantsMinted","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
]""")

BAKC_ABI_FRAGMENT = json.loads("""[
  {"inputs":[],"name":"totalSupply","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
  {"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"isMinted","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"}
]""")


# ── Logging ──────────────────────────────────────────────────────────────────
def setup_logging(name: str = "bayc_family") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
