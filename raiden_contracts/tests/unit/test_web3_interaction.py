import pytest

from raiden_contracts.utils.logs import LogFilter
from raiden_contracts.utils.type_aliases import Address


def test_logfilter_with_nonexistent_event(web3):
    """ Try to create a LogFilter with a nonexistent event """

    with pytest.raises(ValueError):
        LogFilter(
            web3=web3,
            abi=[],
            address=Address("fake"),
            event_name="ev0",
            from_block=0,
            to_block="latest",
        )


def test_call_and_transact_does_not_mine(web3, custom_token):
    """ See call_and_transact() does not mine a block """

    before = web3.eth.blockNumber
    custom_token.functions.multiplier().call_and_transact()
    after = web3.eth.blockNumber
    assert before + 1 == after
