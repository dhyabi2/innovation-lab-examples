"""Tests for the Nano (XNO) on-chain verification module.

These tests exercise the verification logic without depending on the live
public Nano RPC: they mock `verify_nano.nano_rpc_post` to return canned
`account_history` payloads and assert the decide logic (amount threshold,
confirmation flag, timestamp window). This keeps CI deterministic and offline.
"""

import sys

from unittest import mock

sys.path.insert(0, ".")

import verify_nano  # noqa: E402


class _Logger:
    def __init__(self):
        self.lines = []

    def info(self, *args):
        self.lines.append(("info", args))

    def error(self, *args):
        self.lines.append(("error", args))


def _receive(amount_raw, ts, confirmed=True, h="ABCDEF"):
    return {
        "type": "receive",
        "account": "nano_1hash",
        "amount": str(amount_raw),
        "local_timestamp": str(ts),
        "hash": h,
        "confirmed": "true" if confirmed else "false",
    }


def test_verifies_confirmed_receive_above_threshold():
    now = verify_nano.time.time()
    payload = {
        "history": [
            _receive(int(0.05 * verify_nano.RAW_PER_XNO), int(now - 10), h="AAA")
        ]
    }
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload) as rpc:
        result = verify_nano.verify_nano_receive(
            "nano_1acct", "0.03", lookback_seconds=3600, logger=None
        )
    rpc.assert_called_once()
    assert result == "AAA"


def test_requires_matching_transaction_hash_when_given():
    now = verify_nano.time.time()
    payload = {
        "history": [
            _receive(int(0.05 * verify_nano.RAW_PER_XNO), int(now - 10), h="AAA")
        ]
    }
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        # Hash mismatch -> not verified (the buyer's reported tx does not match).
        assert (
            verify_nano.verify_nano_receive(
                "nano_1acct",
                "0.03",
                lookback_seconds=3600,
                expected_hash="ZZZ",
                logger=None,
            )
            is None
        )
        # Exact match -> verified.
        assert (
            verify_nano.verify_nano_receive(
                "nano_1acct",
                "0.03",
                lookback_seconds=3600,
                expected_hash="AAA",
                logger=None,
            )
            == "AAA"
        )


def test_rejects_receive_below_threshold():
    now = verify_nano.time.time()
    payload = {
        "history": [
            _receive(int(0.001 * verify_nano.RAW_PER_XNO), int(now - 10), h="BBB")
        ]
    }
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        result = verify_nano.verify_nano_receive(
            "nano_1acct", "0.05", lookback_seconds=3600, logger=None
        )
    assert result is None


def test_rejects_unconfirmed_receive():
    now = verify_nano.time.time()
    payload = {
        "history": [
            _receive(
                int(5 * verify_nano.RAW_PER_XNO),
                int(now - 10),
                confirmed=False,
                h="CCC",
            )
        ]
    }
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        result = verify_nano.verify_nano_receive(
            "nano_1acct", "1.0", lookback_seconds=3600, logger=None
        )
    assert result is None


def test_ignores_entries_outside_lookback_window():
    # Entry is far older than the window and must be ignored (and thus not
    # counted, since history is newest-first and older entries stop the scan).
    old_ts = verify_nano.time.time() - 10**7
    payload = {
        "history": [_receive(int(5 * verify_nano.RAW_PER_XNO), int(old_ts), h="DDD")]
    }
    with mock.patch.object(verify_nano, "nano_rpc_post", return_value=payload):
        result = verify_nano.verify_nano_receive(
            "nano_1acct", "1.0", lookback_seconds=3600, logger=None
        )
    assert result is None


def test_returns_none_for_blank_account():
    with mock.patch.object(
        verify_nano, "nano_rpc_post", return_value={"history": []}
    ) as rpc:
        result = verify_nano.verify_nano_receive("", "0.03", logger=None)
    rpc.assert_not_called()
    assert result is None


def test_returns_none_for_invalid_amount():
    with mock.patch.object(
        verify_nano, "nano_rpc_post", return_value={"history": []}
    ) as rpc:
        result = verify_nano.verify_nano_receive(
            "nano_1acct", "not-a-number", logger=None
        )
    rpc.assert_not_called()
    assert result is None


def test_returns_none_for_live_rpc_error():
    with mock.patch.object(
        verify_nano,
        "nano_rpc_post",
        side_effect=RuntimeError("boom"),
    ):
        result = verify_nano.verify_nano_receive("nano_1acct", "0.03", logger=None)
    assert result is None
