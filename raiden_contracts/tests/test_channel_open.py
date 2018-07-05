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
from .fixtures.config import EMPTY_ADDRESS, FAKE_ADDRESS, fake_bytes
from web3.exceptions import ValidationError
from .utils import get_channel_identifier, get_participants_hash


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
        token_network.functions.openChannel(FAKE_ADDRESS, B, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, 0x0, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, '', settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, FAKE_ADDRESS, settle_timeout).transact()

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(EMPTY_ADDRESS, B, settle_timeout).transact()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, EMPTY_ADDRESS, settle_timeout).transact()

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


def test_participants_hash(token_network, get_accounts):
    (A, B) = get_accounts(2)

    AB_hash = get_participants_hash(A, B)
    assert token_network.functions.getParticipantsHash(A, B).call() == AB_hash


def test_counter(token_network, get_accounts, create_channel):
    (A, B, C, D) = get_accounts(4)

    AB_hash = token_network.functions.getParticipantsHash(A, B).call()
    BC_hash = token_network.functions.getParticipantsHash(B, C).call()
    CD_hash = token_network.functions.getParticipantsHash(C, D).call()

    assert token_network.functions.channel_counter().call() == 0
    assert token_network.functions.participants_hash_to_channel_counter(AB_hash).call() == 0
    assert token_network.functions.participants_hash_to_channel_counter(BC_hash).call() == 0
    assert token_network.functions.participants_hash_to_channel_counter(CD_hash).call() == 0

    channel_identifier_no_channel = get_channel_identifier(A, B, 0)
    assert token_network.functions.getChannelIdentifier(
        A,
        B,
    ).call() == channel_identifier_no_channel
    create_channel(A, B)
    channel_identifier = get_channel_identifier(A, B, 1)
    assert token_network.functions.channel_counter().call() == 1
    assert token_network.functions.participants_hash_to_channel_counter(AB_hash).call() == 1
    assert token_network.functions.getChannelIdentifier(A, B).call() == channel_identifier

    channel_identifier_no_channel = get_channel_identifier(B, C, 0)
    assert token_network.functions.getChannelIdentifier(
        B,
        C,
    ).call() == channel_identifier_no_channel
    create_channel(B, C)
    channel_identifier = get_channel_identifier(B, C, 2)
    assert token_network.functions.channel_counter().call() == 2
    assert token_network.functions.participants_hash_to_channel_counter(BC_hash).call() == 2
    assert token_network.functions.getChannelIdentifier(B, C).call() == channel_identifier

    channel_identifier_no_channel = get_channel_identifier(C, D, 0)
    assert token_network.functions.getChannelIdentifier(
        C,
        D,
    ).call() == channel_identifier_no_channel
    create_channel(C, D)
    channel_identifier = get_channel_identifier(C, D, 3)
    assert token_network.functions.channel_counter().call() == 3
    assert token_network.functions.participants_hash_to_channel_counter(CD_hash).call() == 3
    assert token_network.functions.getChannelIdentifier(C, D).call() == channel_identifier


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
