from typing import Any, Dict, Optional, Tuple

from web3 import Web3
from web3.utils.threads import Timeout


def check_successful_tx(
    web3: Web3, txid: str, timeout: int = 180
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt and transaction info
    """
    receipt = wait_for_transaction_receipt(web3=web3, txid=txid, timeout=timeout)
    if receipt is None:
        raise RuntimeError("Could not obtain a transaction receipt.")
    txinfo = web3.eth.getTransaction(txid)
    if "status" not in receipt:
        raise KeyError(
            'A transaction receipt does not contain the "status" field. '
            "Does your chain have Byzantium rules enabled?"
        )
    if receipt["status"] == 0:
        raise ValueError(f"Status 0 indicates failure")
    if txinfo["gas"] == receipt["gasUsed"]:
        raise ValueError(f'Gas is completely used ({txinfo["gas"]}). Failure?')
    return (receipt, txinfo)


def wait_for_transaction_receipt(
    web3: Web3, txid: str, timeout: int = 180
) -> Optional[Dict[str, Any]]:
    receipt = None
    with Timeout(timeout) as time:
        while not receipt or not receipt["blockNumber"]:  # pylint: disable=E1136
            try:
                receipt = web3.eth.getTransactionReceipt(txid)
            except ValueError as ex:
                if str(ex).find("EmptyResponse") != -1:
                    pass  # Empty response from a Parity light client
                else:
                    raise ex
            time.sleep(5)

    return receipt
