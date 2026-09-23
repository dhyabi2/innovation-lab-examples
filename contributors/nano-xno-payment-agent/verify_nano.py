"""
Nano (XNO) on-chain payment verification for the uAgents payment protocol.

Nano is a feeless, single-block-final layer-1: each send publishes one block that
is confirmed within ~0.2s of deterministic ORV finality (no reorgs, no chargebacks,
no settlement window, no gas). This module verifies that an agent account actually
received a Nano payment using the public network RPC — keyless, read-only.

Verification model used here: the seller publishes its Nano receiving account in
RequestPayment.metadata["provider_nano_account"]. The buyer pays by sending XNO to
that account and reports the send block hash as transaction_id. The seller then
checks the account's history for a confirmed receive of at least the requested
amount; if found, the payment is real and final — there is no reversal path.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from typing import Any

# Public Nano RPC (rpc.nano.to). No key required for account_history reads.
# Override with the NANO_RPC_URL env var to point at a private/shared node.
NANO_RPC_URL = os.getenv("NANO_RPC_URL", "https://rpc.nano.to")

RAW_PER_XNO = 10**30


def nano_rpc_post(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """POST a Nano RPC action to the public node and return parsed JSON."""
    payload = json.dumps({"action": action, **params}).encode("utf-8")
    req = urllib.request.Request(
        NANO_RPC_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "uagents-nano-payment-example/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 (https only)
        return json.loads(resp.read().decode("utf-8"))


def verify_nano_receive(
    account: str,
    expected_amount_xno: str | float,
    *,
    lookback_seconds: int = 3600,
    expected_hash: str | None = None,
    logger: Any = None,
) -> str | None:
    """Verify `account` received at least `expected_amount_xno` XNO recently.

    If `expected_hash` is given, the confirmed receive's block hash must match it
    (the buyer's reported `transaction_id`), so one payment cannot verify many
    commits. Returns the verified block hash on success, or None.
    """
    if not account:
        if logger:
            logger.error("No Nano receiving account configured")
        return None
    try:
        expected_raw = int(float(expected_amount_xno) * RAW_PER_XNO)
    except (TypeError, ValueError):
        if logger:
            logger.error(f"Invalid expected amount: {expected_amount_xno}")
        return None

    try:
        data = nano_rpc_post("account_history", {"account": account, "count": "25"})
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.error(f"Nano RPC account_history failed: {exc}")
        return None

    error = data.get("error")
    if error:
        if logger:
            logger.error(f"Nano RPC error: {error}")
        return None

    history = data.get("history", [])
    cutoff = int(time.time()) - lookback_seconds

    if logger:
        logger.info(
            f"Verifying Nano receive for {account}: need "
            f">= {expected_amount_xno} XNO within last {lookback_seconds}s"
        )

    for entry in history:
        # Entries for this account as a recipient come back as type "receive".
        if entry.get("type") != "receive":
            continue
        if entry.get("confirmed") not in (True, "true"):
            continue
        try:
            ts = int(entry.get("local_timestamp", 0))
        except (TypeError, ValueError):
            ts = 0
        if ts < cutoff:
            # History is newest-first; once entries are older than the window we
            # can stop looking.
            break
        try:
            received_raw = int(entry.get("amount", "0"))
        except (TypeError, ValueError):
            received_raw = 0
        if received_raw >= expected_raw:
            received_xno = received_raw / RAW_PER_XNO
            entry_hash = str(entry.get("hash") or "")
            # If the buyer reported a specific transaction (block hash), only
            # that exact receive counts — otherwise one payment could be reused
            # to verify many commits.
            if expected_hash and entry_hash.lower() != str(expected_hash).lower():
                continue
            if logger:
                logger.info(f"Nano payment verified: {entry_hash} ({received_xno} XNO)")
            return entry_hash

    if logger:
        logger.error(
            f"Nano payment NOT verified for {account}: no confirmed receive "
            f"of >= {expected_amount_xno} XNO within the window"
        )
    return None
