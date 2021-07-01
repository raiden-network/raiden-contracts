from typing import Callable

from web3.contract import Contract

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ChannelEvent
from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.utils.events import check_channel_opened, check_new_deposit


def test_channel_open_with_deposit_basics(
    get_accounts: Callable,
    token_network: Contract,
    assign_tokens: Callable,
) -> None:
    """Some basic checks that `open_withDeposit` works.

    Detailed tests exist for `openChannel` and `setTotalDeposit`, and as `openChannelWithDeposit`
    is a simple wrapper, these don't need to be duplicated.
    """
    (A, B, C, D) = get_accounts(4)
    deposit = 100

    # Check channel creation by participant
    assign_tokens(A, deposit)
    call_and_transact(
        token_network.functions.openChannelWithDeposit(A, B, TEST_SETTLE_TIMEOUT_MIN, deposit),
        {"from": A},
    )
    assert token_network.functions.getChannelIdentifier(A, B).call() == 1
    assert token_network.functions.getChannelParticipantInfo(1, A, B).call()[0] == 100
    assert token_network.functions.getChannelParticipantInfo(1, B, A).call()[0] == 0

    # Check channel creation by delegate
    assign_tokens(D, deposit)
    call_and_transact(
        token_network.functions.openChannelWithDeposit(B, C, TEST_SETTLE_TIMEOUT_MIN, deposit),
        {"from": D},
    )
    assert token_network.functions.getChannelIdentifier(B, C).call() == 2
    assert token_network.functions.getChannelParticipantInfo(2, B, C).call()[0] == 100
    assert token_network.functions.getChannelParticipantInfo(2, C, B).call()[0] == 0


def test_channel_open_with_deposit_events(
    get_accounts: Callable,
    token_network: Contract,
    event_handler: Callable,
    assign_tokens: Callable,
) -> None:
    """A successful openChannelWithDeposit() causes an OPENED and DEPOSIT event"""
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit = 100

    assign_tokens(A, deposit)
    txn_hash = call_and_transact(
        token_network.functions.openChannelWithDeposit(A, B, TEST_SETTLE_TIMEOUT_MIN, deposit),
        {"from": A},
    )
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()

    ev_handler.add(
        txn_hash,
        ChannelEvent.OPENED,
        check_channel_opened(channel_identifier, A, B, TEST_SETTLE_TIMEOUT_MIN),
    )
    ev_handler.add(
        txn_hash,
        ChannelEvent.DEPOSIT,
        check_new_deposit(channel_identifier, A, deposit),
    )
    ev_handler.check()
