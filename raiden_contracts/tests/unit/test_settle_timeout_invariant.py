import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MAX, TEST_SETTLE_TIMEOUT_MIN
from raiden_contracts.tests.utils import fake_bytes


def test_settle_timeout_inrange(
        token_network,
        get_accounts,
        web3,
):
    """ The TokenNetwork constructor must enforce that settle timeout is in
    the valid range.

    Also asserts that the constants.py and the netting channel contract values
    are synched.
    """
    (A, B) = get_accounts(2)

    small_settle_timeout = TEST_SETTLE_TIMEOUT_MIN - 1
    large_settle_timeout = TEST_SETTLE_TIMEOUT_MAX + 1

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, small_settle_timeout).call()

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, large_settle_timeout).call()

    token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MIN).call_and_transact()
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()
    (
        settle_block_number,
        _,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()

    assert settle_block_number == TEST_SETTLE_TIMEOUT_MIN

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).call_and_transact({'from': A})
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)
    token_network.functions.settleChannel(
        channel_identifier,
        A,
        0,
        0,
        fake_bytes(32),
        B,
        0,
        0,
        fake_bytes(32),
    ).call_and_transact({'from': A})
    token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MAX).call_and_transact()
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()
    (
        settle_block_number,
        _,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()

    assert settle_block_number == TEST_SETTLE_TIMEOUT_MAX
