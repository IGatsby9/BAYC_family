"""
Thin RPC helper with Multicall3 batching and event-log scanning.
"""
import time
import requests
from typing import Any

from scripts.config import ETH_RPC_URL, setup_logging

log = setup_logging("rpc")

_session = requests.Session()
_rpc_id = 0

MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
# tryAggregate(bool requireSuccess, (address target, bytes callData)[] calls)
TRYAGGREGATE_SIG = "0xbce38bd7"


def _next_id() -> int:
    global _rpc_id
    _rpc_id += 1
    return _rpc_id


def rpc_call(method: str, params: list, url: str = ETH_RPC_URL) -> Any:
    """Single JSON-RPC call with retry + back-off."""
    payload = {"jsonrpc": "2.0", "id": _next_id(), "method": method, "params": params}
    for attempt in range(8):
        try:
            resp = _session.post(url, json=payload, timeout=120)

            if resp.status_code == 429 or resp.status_code >= 500:
                wait = min(2 ** attempt, 30)
                log.warning("HTTP %d (attempt %d), waiting %ds …", resp.status_code, attempt + 1, wait)
                time.sleep(wait)
                continue

            if not resp.text.strip():
                wait = min(2 ** attempt, 30)
                log.warning("Empty response (attempt %d), waiting %ds …", attempt + 1, wait)
                time.sleep(wait)
                continue

            body = resp.json()
            if "error" in body:
                err_msg = body["error"].get("message", str(body["error"]))
                if any(kw in err_msg.lower() for kw in ("limit", "rate", "too many", "capacity")):
                    wait = min(2 ** attempt, 30)
                    log.warning("Rate-limited (attempt %d), waiting %ds …", attempt + 1, wait)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"RPC error: {err_msg}")
            return body.get("result")

        except (requests.ConnectionError, requests.Timeout, requests.exceptions.JSONDecodeError) as exc:
            wait = min(2 ** attempt, 30)
            log.warning("Request issue (attempt %d): %s — retrying in %ds", attempt + 1, type(exc).__name__, wait)
            time.sleep(wait)

    raise RuntimeError(f"RPC call {method} failed after 8 attempts")


def get_block_number() -> int:
    hex_block = rpc_call("eth_blockNumber", [])
    return int(hex_block, 16)


def get_transaction(tx_hash: str) -> dict:
    return rpc_call("eth_getTransactionByHash", [tx_hash])


def eth_call(to: str, data: str) -> str:
    """Single eth_call."""
    return rpc_call("eth_call", [{"to": to, "data": data}, "latest"])


# ── ABI encoding helpers ────────────────────────────────────────────────────

def _encode_uint256(v: int) -> str:
    return f"{v:064x}"


def _encode_address(addr: str) -> str:
    return addr.lower().replace("0x", "").zfill(64)


def _encode_call(target: str, calldata: str) -> str:
    """Encode a single (address, bytes) tuple for Multicall3."""
    addr = _encode_address(target)
    offset_placeholder = ""  # will be set in batch
    return addr, calldata


# ── Multicall3 batching ────────────────────────────────────────────────────

def multicall_tryaggregate(
    calls: list[tuple[str, str]],
    batch_size: int = 200,
    delay: float = 0.35,
) -> list[tuple[bool, bytes]]:
    """
    Batch eth_call via Multicall3.tryAggregate(false, calls[]).
    Each call is (target_address, calldata_hex_with_0x_prefix).
    Returns list of (success, returnData) tuples.
    """
    all_results: list[tuple[bool, bytes]] = []

    for i in range(0, len(calls), batch_size):
        batch = calls[i : i + batch_size]
        calldata = _encode_tryaggregate(batch)
        raw = rpc_call("eth_call", [{"to": MULTICALL3, "data": calldata}, "latest"])
        results = _decode_tryaggregate_result(raw, len(batch))
        all_results.extend(results)

        if i + batch_size < len(calls) and delay > 0:
            time.sleep(delay)

        done = min(i + batch_size, len(calls))
        if done % 2000 == 0 or done == len(calls):
            log.info("  multicall progress: %d / %d", done, len(calls))

    return all_results


def _encode_tryaggregate(calls: list[tuple[str, str]]) -> str:
    """
    ABI-encode tryAggregate(false, (address,bytes)[] calls).
    """
    # requireSuccess = false → 0
    # calls is a dynamic array at offset 64 (0x40)
    parts = [TRYAGGREGATE_SIG[2:]]  # remove 0x

    # requireSuccess (bool) = false
    parts.append(_encode_uint256(0))
    # offset to calls array
    parts.append(_encode_uint256(64))
    # calls array length
    parts.append(_encode_uint256(len(calls)))

    # For each call: offset into the tail section
    # Each call struct has: address (32 bytes) + offset to bytes (32 bytes) + bytes length (32 bytes) + bytes data (padded)
    # But dynamic arrays of structs need offsets first, then data

    # Calculate offsets for each call's data
    # After the N offset words, each call's encoded data follows
    offsets = []
    current_offset = len(calls) * 32  # past all the offset words

    call_encodings = []
    for target, cd in calls:
        enc = _encode_single_call(target, cd)
        call_encodings.append(enc)
        offsets.append(current_offset)
        current_offset += len(enc) // 2  # hex chars -> bytes

    for off in offsets:
        parts.append(_encode_uint256(off))

    for enc in call_encodings:
        parts.append(enc)

    return "0x" + "".join(parts)


def _encode_single_call(target: str, calldata: str) -> str:
    """Encode (address target, bytes callData) struct."""
    cd_bytes = bytes.fromhex(calldata.replace("0x", ""))
    cd_len = len(cd_bytes)
    cd_padded_len = ((cd_len + 31) // 32) * 32

    parts = []
    parts.append(_encode_address(target))
    parts.append(_encode_uint256(64))  # offset to bytes data (after address + this offset word)
    parts.append(_encode_uint256(cd_len))
    parts.append(cd_bytes.hex().ljust(cd_padded_len * 2, '0'))
    return "".join(parts)


def _decode_tryaggregate_result(raw: str, expected_count: int) -> list[tuple[bool, bytes]]:
    """Decode the return data from tryAggregate."""
    data = bytes.fromhex(raw.replace("0x", ""))
    # Return type: (bool success, bytes returnData)[]
    # First 32 bytes: offset to array
    arr_offset = int.from_bytes(data[0:32], 'big')
    arr_len = int.from_bytes(data[arr_offset:arr_offset+32], 'big')

    results = []
    # Read offsets for each element
    elem_offsets = []
    for i in range(arr_len):
        off = int.from_bytes(data[arr_offset+32+i*32 : arr_offset+64+i*32], 'big')
        elem_offsets.append(arr_offset + 32 + off)

    for off in elem_offsets:
        success = int.from_bytes(data[off:off+32], 'big') != 0
        bytes_offset = int.from_bytes(data[off+32:off+64], 'big')
        bytes_len = int.from_bytes(data[off+bytes_offset:off+bytes_offset+32], 'big')
        ret_data = data[off+bytes_offset+32:off+bytes_offset+32+bytes_len]
        results.append((success, ret_data))

    return results


# ── Event log scanning ──────────────────────────────────────────────────────

def get_logs(address: str, topics: list, from_block: int, to_block: int) -> list[dict]:
    params = {
        "address": address,
        "topics": topics,
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
    }
    return rpc_call("eth_getLogs", [params])


def scan_logs(
    address: str,
    topics: list,
    start_block: int,
    end_block: int,
    initial_chunk: int = 2_000,
    min_chunk: int = 200,
    inter_chunk_delay: float = 0.4,
) -> list[dict]:
    """
    Scan event logs across a large block range with adaptive chunk sizing.
    """
    all_logs: list[dict] = []
    chunk_size = initial_chunk
    current = start_block
    total_range = end_block - start_block
    chunks_done = 0

    while current <= end_block:
        chunk_end = min(current + chunk_size - 1, end_block)
        try:
            logs = get_logs(address, topics, current, chunk_end)
            if logs is None:
                logs = []
            all_logs.extend(logs)
            chunks_done += 1
            pct = ((current - start_block) / total_range * 100) if total_range > 0 else 100
            if logs:
                log.info(
                    "  blocks %s–%s → %d events (total %d) [%.0f%%]",
                    f"{current:,}", f"{chunk_end:,}", len(logs), len(all_logs), pct,
                )
            elif chunks_done % 100 == 0:
                log.info("  progress: block %s [%.0f%%] — %d events so far",
                         f"{current:,}", pct, len(all_logs))
            current = chunk_end + 1
            chunk_size = min(chunk_size * 2, initial_chunk)
            if inter_chunk_delay > 0:
                time.sleep(inter_chunk_delay)
        except RuntimeError as exc:
            err = str(exc).lower()
            if any(kw in err for kw in ("exceed", "range", "too large", "limit", "response size", "block range")):
                chunk_size = max(chunk_size // 2, min_chunk)
                log.info("  shrinking chunk to %d blocks", chunk_size)
                if chunk_size < min_chunk:
                    raise RuntimeError(f"Chunk size below minimum ({min_chunk}), aborting") from exc
            else:
                raise

    return all_logs


def parse_transfer_log(log_entry: dict) -> dict:
    """Parse an ERC-721 Transfer event log."""
    topics = log_entry["topics"]
    return {
        "from": "0x" + topics[1][-40:],
        "to": "0x" + topics[2][-40:],
        "token_id": int(topics[3], 16),
        "tx_hash": log_entry["transactionHash"],
        "block_number": int(log_entry["blockNumber"], 16),
        "log_index": int(log_entry["logIndex"], 16),
    }
