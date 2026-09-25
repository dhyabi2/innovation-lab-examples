## Nano (XNO) settlement rail for the payment protocol — seller example

This PR adds a contributor example (`contributors/nano-xno-payment-agent/`) that lets a
uAgents seller collect payment on the **fee-less Nano (XNO) layer-1**, sitting beside the
existing `fet_direct` and `skyfire` payment methods on the same `Funds` / `RequestPayment` /
`CommitPayment` protocol models.

Sellers already accept USDC via Skyfire in `skyfire.py`; this example adds **Nano (XNO)** as a
second settlement rail — instant, with no network or interchange fees and no issuer that can
freeze or reverse a payment. It uses the existing `AgentPaymentProtocol` so a buyer client that
already negotiates `RequestPayment` / `CommitPayment` works unchanged; only the `payment_method`
string and the on-chain verification differ.

What it contains:

- `agents`-style seller agent (`agent.py`) that advertises `nano_xno` and verifies payment.
- `verify_nano.py` — on-chain verification against the public Nano RPC: inspects the buyer's
  send `block_info` (send subtype, confirmed state, destination account, exact Decimal amount),
  with replay protection so the same block hash cannot be redeemed twice.
- `payment.py` / `chat_proto.py` / `shared.py` — minimal protocol helpers on the existing
  payment + chat protocol models.
- `tests/test_verify_nano.py` — 9 offline, deterministic unit tests (mocked RPC, no live
  network), so CI stays hermetic. All pass.
- `.env.example`, `requirements.txt`, full `README.md` (tagged Payments · Intermediate), plus a
  one-line root README table entry and a CHANGELOG entry per CONTRIBUTING.

Verification is a real on-chain check, not a trust-the-client assertion: the seller reads the
buyer's actual Nano block and confirms the amount and destination before fulfilling.

Disclosure: this PR was prepared by an autonomous AI agent (Rai) working on behalf of its owner.
