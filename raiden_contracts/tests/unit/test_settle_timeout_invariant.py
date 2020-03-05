from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MAX, TEST_SETTLE_TIMEOUT_MIN
from raiden_contracts.tests.utils import LOCKSROOT_OF_NO_LOCKS, call_and_transact, fake_bytes
from raiden_contracts.tests.utils.blockchain import mine_blocks


def test_settle_timeout_inrange(
    token_network: Contract,
    get_accounts: Callable,
    web3: Web3,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
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

    call_and_transact(token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MIN))
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()
    (settle_block_number, _) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()

    assert settle_block_number == TEST_SETTLE_TIMEOUT_MIN

    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier=channel_identifier,
            non_closing_participant=B,
            closing_participant=A,
            balance_hash=fake_bytes(32),
            nonce=0,
            additional_hash=fake_bytes(32),
            non_closing_signature=fake_bytes(65),
            closing_signature=closing_sig,
        ),
        {"from": A},
    )
    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier, A, 0, 0, LOCKSROOT_OF_NO_LOCKS, B, 0, 0, LOCKSROOT_OF_NO_LOCKS
        ),
        {"from": A},
    )
    call_and_transact(token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MAX))
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()
    (settle_block_number, _) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()

    assert settle_block_number == TEST_SETTLE_TIMEOUT_MAX
