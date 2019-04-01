from typing import Dict, Tuple

from web3 import Web3
from web3.contract import ContractFunction
from web3.utils.threads import Timeout


def check_successful_tx(web3: Web3, txid: str, timeout=180) -> Tuple[dict, dict]:
    """See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt and transaction info
    """
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    txinfo = web3.eth.getTransaction(txid)
    if receipt['status'] == 0:
        raise ValueError(f'Status 0 indicates failure')
    if txinfo['gas'] == receipt['gasUsed']:
        raise ValueError(f'Gas is completely used ({txinfo["gas"]}). Failure?')
    return (receipt, txinfo)


def wait_for_transaction_receipt(web3, txid, timeout=180):
    receipt = None
    with Timeout(timeout) as time:
            while not receipt or not receipt['blockNumber']:  # pylint: disable=E1136
                try:
                    receipt = web3.eth.getTransactionReceipt(txid)
                except ValueError as ex:
                    if str(ex).find('EmptyResponse') != -1:
                        pass  # Empty response from a Parity light client
                    else:
                        raise ex
                time.sleep(1)

    return receipt


def transact_for_success(
        web3: Web3,
        contract_function: ContractFunction,
        transaction_params: Dict,
) -> Dict:
    """ Executes contract_function.transact(transaction_params) and checks success

    raises TransactionFailed when the receipt indicates failure. """
    txid = contract_function.transact(transaction_params)
    receipt = wait_for_transaction_receipt(web3=web3, txid=txid)
    if 'status' not in receipt:
        raise NotImplementedError(
            'A transaction receipt does not contain "status" field.'
            'Maybe the chain is running rules older than Byzantium.',
        )
    if receipt['status'] == 0:
        raise RuntimeError('Transaction receipt indicates failure.')
    return receipt
