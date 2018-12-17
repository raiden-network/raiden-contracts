from web3 import Web3
from web3.utils.threads import (
    Timeout,
)


def check_succesful_tx(web3: Web3, txid: str, timeout=180) -> dict:
    '''See if transaction went through (Solidity code did not throw).
    :return: Transaction receipt
    '''
    receipt = wait_for_transaction_receipt(web3, txid, timeout=timeout)
    txinfo = web3.eth.getTransaction(txid)
    assert receipt['status'] != 0
    assert txinfo['gas'] != receipt['gasUsed']
    return receipt


def wait_for_transaction_receipt(web3, txid, timeout=180):
    with Timeout(timeout) as time:
            while not web3.eth.getTransactionReceipt(txid):
                time.sleep(5)

    return web3.eth.getTransactionReceipt(txid)
