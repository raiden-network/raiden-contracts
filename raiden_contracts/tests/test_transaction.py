from unittest.mock import Mock

import pytest
from hexbytes import HexBytes
from web3.types import TxData, TxReceipt, Wei

from raiden_contracts.utils.transaction import check_successful_tx


def test_check_successful_tx_with_status_zero() -> None:
    web3_mock = Mock()
    web3_mock.eth.getTransactionReceipt.return_value = {"blockNumber": 300, "status": 0}
    txid = HexBytes("abcdef")
    with pytest.raises(ValueError):
        check_successful_tx(web3=web3_mock, txid=txid)
    web3_mock.eth.getTransactionReceipt.assert_called_with(txid)
    web3_mock.eth.getTransaction.assert_called_with(txid)


def test_check_successful_tx_with_nonexistent_status() -> None:
    """ check_successful_tx() with a receipt without status field should raise a KeyError """
    web3_mock = Mock()
    web3_mock.eth.getTransactionReceipt.return_value = {"blockNumber": 300}
    txid = HexBytes("abcdef")
    with pytest.raises(KeyError):
        check_successful_tx(web3=web3_mock, txid=txid)
    web3_mock.eth.getTransactionReceipt.assert_called_with(txid)
    web3_mock.eth.getTransaction.assert_called_with(txid)


def test_check_successful_tx_with_gas_completely_used() -> None:
    web3_mock = Mock()
    gas = 30000
    web3_mock.eth.getTransactionReceipt.return_value = {
        "blockNumber": 300,
        "status": 1,
        "gasUsed": gas,
    }
    web3_mock.eth.getTransaction.return_value = {"gas": gas}
    txid = HexBytes("abcdef")
    with pytest.raises(ValueError):
        check_successful_tx(web3=web3_mock, txid=txid)
    web3_mock.eth.getTransactionReceipt.assert_called_with(txid)
    web3_mock.eth.getTransaction.assert_called_with(txid)


def test_check_successful_tx_successful_case() -> None:
    web3_mock = Mock()
    gas = 30000
    receipt = TxReceipt({"blockNumber": 300, "status": 1, "gasUsed": gas - 10})  # type: ignore
    web3_mock.eth.getTransactionReceipt.return_value = receipt
    txinfo = TxData({"gas": Wei(gas)})
    web3_mock.eth.getTransaction.return_value = txinfo
    txid = HexBytes("abcdef")
    assert check_successful_tx(web3=web3_mock, txid=txid) == (receipt, txinfo)
    web3_mock.eth.getTransactionReceipt.assert_called_with(txid)
    web3_mock.eth.getTransaction.assert_called_with(txid)
