"""Blockchain integration service — web3.py v7 compatible.

Connects to a local Hardhat node (http://127.0.0.1:8545) and interacts with
the deployed DocumentRegistry contract.

Exported functions
------------------
register_document(document_id, document_hash) -> dict
    Sends a real on-chain transaction.  Returns
    {"registered": True, "transaction_hash": "0x...", "document_hash": "..."}

verify_document(document_id, document_hash) -> bool
    Calls verifyDocument() on-chain.

get_document(document_id) -> dict | None
    Returns {"document_id", "document_hash", "timestamp"} or None.

get_registered_record(document_id) -> dict | None
    Alias for get_document(); used by routes/blockchain.py.

_sha256(text) -> str
    Helper: SHA-256 hex digest of a UTF-8 string.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, Optional

from web3 import Web3
from eth_account import Account

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WEB3_RPC = os.environ.get("WEB3_RPC_URL", "http://127.0.0.1:8545")

_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "blockchain")
CONTRACT_ADDR_PATH = os.path.join(_BASE, "DocumentRegistry.address.txt")
CONTRACT_ABI_PATH  = os.path.join(_BASE, "DocumentRegistry.abi.json")

PRIVATE_KEY = os.environ.get("PRIVATE_KEY")  # optional; uses node account #0 if absent

# ---------------------------------------------------------------------------
# Web3 connection
# ---------------------------------------------------------------------------

_w3 = Web3(Web3.HTTPProvider(WEB3_RPC))


def _load_contract():
    """Load contract ABI + address and return a Contract object."""
    try:
        with open(CONTRACT_ABI_PATH, "r") as f:
            loaded = json.load(f)
            abi = loaded.get("abi", loaded)      # handle both raw-array and artifact JSON
        with open(CONTRACT_ADDR_PATH, "r") as f:
            address = f.read().strip()
        contract = _w3.eth.contract(
            address=Web3.to_checksum_address(address),   # web3 v7: class-level method
            abi=abi,
        )
        return contract, address
    except Exception as exc:
        raise RuntimeError(f"Cannot load contract: {exc}") from exc


# ---------------------------------------------------------------------------
# SHA-256 helper
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register_document(document_id: str, document_hash: str) -> Dict:
    """Register a document on-chain.

    Uses PRIVATE_KEY if set; otherwise uses the first unlocked account
    exposed by the Hardhat node (account #0, which is pre-funded).
    """
    if not _w3.is_connected():
        raise RuntimeError(f"Cannot connect to Ethereum node at {WEB3_RPC}")

    contract, _ = _load_contract()

    if PRIVATE_KEY:
        acct = Account.from_key(PRIVATE_KEY)
        nonce = _w3.eth.get_transaction_count(acct.address)
        tx = contract.functions.registerDocument(document_id, document_hash).build_transaction({
            "chainId":  _w3.eth.chain_id,
            "from":     acct.address,
            "nonce":    nonce,
            "gas":      300_000,
            "gasPrice": _w3.eth.gas_price,
        })
        signed   = acct.sign_transaction(tx)
        tx_hash  = _w3.eth.send_raw_transaction(signed.raw_transaction)  # v7: raw_transaction
    else:
        # Hardhat unlocked account — no signing needed
        accounts = _w3.eth.accounts
        if not accounts:
            raise RuntimeError("No accounts available on node and PRIVATE_KEY not set")

        tx_hash = contract.functions.registerDocument(document_id, document_hash).transact({
            "from": accounts[0],
            "gas":  300_000,
        })

    receipt = _w3.eth.wait_for_transaction_receipt(tx_hash)
    tx_hex  = tx_hash.hex() if isinstance(tx_hash, bytes) else str(tx_hash)

    return {
        "registered":       True,
        "transaction_hash": tx_hex,
        "document_hash":    document_hash,
        "block_number":     receipt["blockNumber"],
    }


def verify_document(document_id: str, document_hash: str) -> bool:
    """Return True if the on-chain hash matches document_hash."""
    if not _w3.is_connected():
        return False
    contract, _ = _load_contract()
    try:
        return bool(contract.functions.verifyDocument(document_id, document_hash).call())
    except Exception:
        return False


def get_document(document_id: str) -> Optional[Dict]:
    """Fetch the on-chain record for document_id."""
    if not _w3.is_connected():
        return None
    contract, _ = _load_contract()
    try:
        doc_id, doc_hash, ts = contract.functions.getDocument(document_id).call()
        if not doc_id:
            return None
        return {"document_id": doc_id, "document_hash": doc_hash, "timestamp": ts}
    except Exception:
        return None


# Alias used by routes/blockchain.py
def get_registered_record(document_id: str) -> Optional[Dict]:
    return get_document(document_id)
