from typing import Tuple

from hexbytes import HexBytes
from web3 import Web3
from web3.types import TxData, TxReceipt


def check_successful_tx(
    web3: Web3, txid: HexBytes, timeout: int = 180
) -> Tuple[TxReceipt, TxData]:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt and transaction info
    """
    receipt = web3.eth.wait_for_transaction_receipt(txid, timeout=timeout)
    if receipt is None:
        raise RuntimeError("Could not obtain a transaction receipt.")
    txinfo = web3.eth.get_transaction(txid)
    if "status" not in receipt:
        raise KeyError(
            'A transaction receipt does not contain the "status" field. '
            "Does your chain have Byzantium rules enabled?"
        )
    if receipt["status"] == 0:
        raise ValueError("Status 0 indicates failure")
    if txinfo["gas"] == receipt["gasUsed"]:
        raise ValueError(f'Gas is completely used ({txinfo["gas"]}). Failure?')
    return receipt, txinfo
