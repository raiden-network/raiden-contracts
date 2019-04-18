import pytest

from raiden_contracts.utils.logs import LogFilter


def test_logfilter_with_nonexistent_event(web3):
    """ Try to create a LogFilter with a nonexistent event """

    with pytest.raises(ValueError):
        LogFilter(
            web3=web3,
            abi=[],
            address='fake',
            event_name='ev0',
            from_block=0,
            to_block='latest',
        )
