import pytest
from eth_typing import BlockNumber
from eth_utils.address import to_checksum_address
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.utils.logs import LogFilter


def test_logfilter_with_nonexistent_event(web3: Web3) -> None:
    """ Try to create a LogFilter with a nonexistent event """

    with pytest.raises(ValueError):
        LogFilter(
            web3=web3,
            abi=[],
            address=to_checksum_address("0xfake"),
            event_name="ev0",
            from_block=BlockNumber(0),
            to_block="latest",
        )


def test_call_and_transact_does_not_mine(web3: Web3, custom_token: Contract) -> None:
    """ See call_and_transact() does not mine a block """

    before = web3.eth.blockNumber
    call_and_transact(custom_token.functions.multiplier())
    after = web3.eth.blockNumber
    assert before + 1 == after
