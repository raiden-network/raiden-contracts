import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.constants import (
    EVENT_CHANNEL_OPENED,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
    CHANNEL_STATE_NONEXISTENT,
    CHANNEL_STATE_OPENED,
)
from raiden_contracts.utils.events import check_channel_opened
from .fixtures.config import empty_address, fake_address, fake_bytes
from web3.exceptions import ValidationError


def test_open_channel_call(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN + 10
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, B, -3).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(0x0, B, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel('', B, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(fake_address, B, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, 0x0, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, '', settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, fake_address, settle_timeout).transact()

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(empty_address, B, settle_timeout).transact()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, empty_address, settle_timeout).transact()

    # Cannot open a channel between 2 participants with the same address
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, A, settle_timeout).transact()

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MIN - 1).transact()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MAX + 1).transact()


def test_max_1_channel(token_network, get_accounts, create_channel):
    (A, B) = get_accounts(2)
    create_channel(A, B, TEST_SETTLE_TIMEOUT_MIN)

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MIN).transact()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(B, A, TEST_SETTLE_TIMEOUT_MIN).transact()


def test_open_channel_state(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN + 10

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert settle_block_number == 0
    assert state == CHANNEL_STATE_NONEXISTENT

    token_network.functions.openChannel(A, B, settle_timeout).transact()

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert settle_block_number == settle_timeout
    assert state == CHANNEL_STATE_OPENED

    (
        A_deposit,
        A_withdrawn,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
    ) = token_network.functions.getChannelParticipantInfo(A, B).call()
    assert A_deposit == 0
    assert A_withdrawn == 0
    assert A_is_the_closer is False
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    (
        B_deposit,
        B_withdrawn,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
    ) = token_network.functions.getChannelParticipantInfo(B, A).call()
    assert B_deposit == 0
    assert B_withdrawn == 0
    assert B_is_the_closer is False
    assert B_balance_hash == fake_bytes(32)
    assert B_nonce == 0


def test_reopen_channel(
        web3,
        token_network,
        get_accounts,
):
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    locksroot = fake_bytes(32)

    token_network.functions.openChannel(A, B, settle_timeout).transact()

    # Opening twice fails
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, settle_timeout).transact()

    # Close channel
    token_network.functions.closeChannel(
        B,
        locksroot,
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})

    # Reopen Channel before settlement fails
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, settle_timeout).transact()

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    # Settle channel
    token_network.functions.settleChannel(
        A,
        0,
        0,
        locksroot,
        B,
        0,
        0,
        locksroot,
    ).transact({'from': A})

    # Reopening the channel should work iff channel is settled
    token_network.functions.openChannel(A, B, settle_timeout).transact()

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert settle_block_number == settle_timeout
    assert state == CHANNEL_STATE_OPENED

    (
        A_deposit,
        A_withdrawn,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
    ) = token_network.functions.getChannelParticipantInfo(A, B).call()
    assert A_deposit == 0
    assert A_withdrawn == 0
    assert A_is_the_closer is False
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    (
        B_deposit,
        B_withdrawn,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
    ) = token_network.functions.getChannelParticipantInfo(B, A).call()
    assert B_deposit == 0
    assert B_withdrawn == 0
    assert B_is_the_closer is False
    assert B_balance_hash == fake_bytes(32)
    assert B_nonce == 0


def test_open_channel_event(get_accounts, token_network, event_handler):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    txn_hash = token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MIN).transact()
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()

    ev_handler.add(
        txn_hash,
        EVENT_CHANNEL_OPENED,
        check_channel_opened(channel_identifier, A, B, TEST_SETTLE_TIMEOUT_MIN),
    )
    ev_handler.check()
