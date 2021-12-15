from typing import Callable

from web3.contract import Contract

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT
from raiden_contracts.tests.utils import LOCKSROOT_OF_NO_LOCKS, call_and_transact, fake_bytes


def test_settle_timeout_inrange(
    token_network: Contract,
    get_accounts: Callable,
    create_close_signature_for_no_balance_proof: Callable,
    time_travel: Callable,
    get_block_timestamp: Callable,
) -> None:
    """The TokenNetwork constructor must enforce that settle timeout is in
    the valid range.

    Also asserts that the constants.py and the netting channel contract values
    are synched.
    """
    (A, B) = get_accounts(2)

    call_and_transact(token_network.functions.openChannel(A, B))
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()
    (settle_window, _) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()

    assert settle_window == TEST_SETTLE_TIMEOUT

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

    time_travel(get_block_timestamp() + settle_window + 2)

    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier,
            A,
            0,
            0,
            LOCKSROOT_OF_NO_LOCKS,
            B,
            0,
            0,
            LOCKSROOT_OF_NO_LOCKS,
        ),
        {"from": A},
    )
    call_and_transact(token_network.functions.openChannel(A, B))
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()
    (settle_window, _) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()

    assert settle_window == TEST_SETTLE_TIMEOUT
