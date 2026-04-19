"""
Register this TEE extension on the Flare network.

Required env vars:
  TEE_PRIVATE_KEY        — private key of the TEE (hex, 0x-prefixed)
  FLARE_RPC_URL          — Flare JSON-RPC endpoint
  REGISTRY_CONTRACT      — address of the TEE registry contract
  CALLER_PRIVATE_KEY     — key of the account paying gas (may equal TEE_PRIVATE_KEY)

Optional:
  REGISTER_FUNCTION      — function signature (default: "registerExtension(address,bytes)")
  FLARE_CHAIN_ID         — chain ID (default: 14 for Flare mainnet, 114 for Coston2)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import coincurve
from eth_abi import encode

from base.crypto import keccak256
from base.encoding import bytes_to_hex, hex_to_bytes
from base.signer import Signer


# ── helpers ──────────────────────────────────────────────────────────────────

def _rpc(url: str, method: str, params: list) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _sign_tx(raw_tx: dict, private_key_bytes: bytes, chain_id: int) -> str:
    """Sign an EIP-155 transaction and return raw hex."""
    # RLP encode + sign — simplified using eth_abi for the data portion only.
    # For a full production implementation use web3.py or eth-account.
    raise NotImplementedError(
        "Full transaction signing requires eth-account. Install it with:\n"
        "  pip install eth-account\n"
        "Then replace this function with:\n"
        "  from eth_account import Account\n"
        "  signed = Account.sign_transaction(raw_tx, private_key)\n"
        "  return signed.rawTransaction.hex()"
    )


def _function_selector(sig: str) -> bytes:
    return keccak256(sig.encode())[:4]


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    rpc_url           = os.environ["FLARE_RPC_URL"]
    registry_contract = os.environ["REGISTRY_CONTRACT"]
    fn_sig            = os.environ.get("REGISTER_FUNCTION", "registerExtension(address,bytes)")
    chain_id          = int(os.environ.get("FLARE_CHAIN_ID", "14"))

    signer = Signer()
    tee_address = signer.address
    tee_pubkey  = bytes.fromhex(signer.public_key_hex().removeprefix("0x"))

    selector = _function_selector(fn_sig)
    call_data = selector + encode(["address", "bytes"], [tee_address, tee_pubkey])

    print(f"TEE address  : {tee_address}")
    print(f"TEE pubkey   : {bytes_to_hex(tee_pubkey)}")
    print(f"Registry     : {registry_contract}")
    print(f"Function     : {fn_sig}")
    print(f"Chain ID     : {chain_id}")
    print(f"Call data    : {bytes_to_hex(call_data)}")
    print()

    # Dry-run: eth_call to check the call won't revert
    result = _rpc(rpc_url, "eth_call", [
        {"to": registry_contract, "data": bytes_to_hex(call_data)},
        "latest",
    ])
    if result.get("error"):
        print(f"eth_call failed: {result['error']}")
        sys.exit(1)
    print(f"eth_call OK — result: {result.get('result')}")
    print()

    # Prompt before sending
    confirm = input("Send registration transaction? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    caller_key_hex = os.environ.get("CALLER_PRIVATE_KEY", os.environ.get("TEE_PRIVATE_KEY", ""))
    if not caller_key_hex:
        print("Set CALLER_PRIVATE_KEY to send the transaction.")
        sys.exit(1)

    caller_key = coincurve.PrivateKey(hex_to_bytes(caller_key_hex.removeprefix("0x")))
    caller_pub = caller_key.public_key.format(compressed=False)[1:]
    caller_address = "0x" + keccak256(caller_pub)[-20:].hex()

    nonce_res = _rpc(rpc_url, "eth_getTransactionCount", [caller_address, "latest"])
    nonce = int(nonce_res["result"], 16)

    gas_price_res = _rpc(rpc_url, "eth_gasPrice", [])
    gas_price = int(gas_price_res["result"], 16)

    raw_tx = {
        "nonce": nonce,
        "gasPrice": gas_price,
        "gas": 200_000,
        "to": registry_contract,
        "value": 0,
        "data": bytes_to_hex(call_data),
        "chainId": chain_id,
    }

    try:
        raw_hex = _sign_tx(raw_tx, caller_key.secret, chain_id)
    except NotImplementedError as e:
        print(e)
        print("\nAlternatively, send the transaction manually via MetaMask or cast:")
        print(f"  cast send {registry_contract} '{fn_sig}' {tee_address} {bytes_to_hex(tee_pubkey)} \\")
        print(f"    --rpc-url {rpc_url} --private-key $CALLER_PRIVATE_KEY")
        return

    tx_res = _rpc(rpc_url, "eth_sendRawTransaction", [raw_hex])
    if tx_res.get("error"):
        print(f"Transaction failed: {tx_res['error']}")
        sys.exit(1)
    print(f"Transaction sent: {tx_res['result']}")


if __name__ == "__main__":
    main()
