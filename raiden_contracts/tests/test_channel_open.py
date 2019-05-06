from itertools import permutations

import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError

from raiden_contracts.constants import (
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
    ChannelEvent,
    ChannelInfoIndex,
    ChannelState,
    ParticipantInfoIndex,
)
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_ADDRESS,
    EMPTY_BALANCE_HASH,
    EMPTY_LOCKSROOT,
    EMPTY_SIGNATURE,
    FAKE_ADDRESS,
)
from raiden_contracts.utils.events import check_channel_opened

from .utils import get_participants_hash


def test_open_channel_call(token_network, get_accounts):
    """ Calling openChannel() with various wrong arguments """
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN + 10

    # Validation failure with a negative settle timeout
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, B, -3)

    # Validation failure with the number zero instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(0x0, B, settle_timeout)

    # Validation failure with the empty string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.openChannel("", B, settle_timeout)

    # Validation failure with an odd-length string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(FAKE_ADDRESS, B, settle_timeout)

    # Validation failure with the number zero instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, 0x0, settle_timeout)

    # Validation failure with the empty string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, "", settle_timeout)

    # Validation failure with an odd-length string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, FAKE_ADDRESS, settle_timeout)

    # Transaction failure with the zero address
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(EMPTY_ADDRESS, B, settle_timeout).call()

    # Transaction failure with the zero address
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, EMPTY_ADDRESS, settle_timeout).call()

    # Cannot open a channel between 2 participants with the same address
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, A, settle_timeout).call()

    # Cannot open a channel for one-too-small settle timeout
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MIN - 1).call()

    # Cannot open a channel for one-too-big settle timeout
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MAX + 1).call()


def test_max_1_channel(token_network, get_accounts, create_channel):
    """ For two participants, at most one channel can be opened """
    (A, B) = get_accounts(2)
    create_channel(A, B, TEST_SETTLE_TIMEOUT_MIN)

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, TEST_SETTLE_TIMEOUT_MIN).call()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(B, A, TEST_SETTLE_TIMEOUT_MIN).call()


def test_participants_hash(token_network, get_accounts):
    """ getParticipantsHash() behaves as get_participants_hash """
    (A, B) = get_accounts(2)

    AB_hash = get_participants_hash(A, B)
    assert token_network.functions.getParticipantsHash(A, B).call() == AB_hash
    assert token_network.functions.getParticipantsHash(B, A).call() == AB_hash


def test_participants_hash_equal(token_network, get_accounts):
    """ getParticipantsHash() behaves as get_participants_hash on equal addresses """
    (A,) = get_accounts(1)

    with pytest.raises(ValueError):
        get_participants_hash(A, A)
    with pytest.raises(TransactionFailed):
        token_network.functions.getParticipantsHash(A, A).call()


def test_counter(token_network, get_accounts, create_channel):
    """ Open three channels and observe states """
    (A, B, C, D) = get_accounts(4)

    AB_hash = token_network.functions.getParticipantsHash(A, B).call()
    BC_hash = token_network.functions.getParticipantsHash(B, C).call()
    CD_hash = token_network.functions.getParticipantsHash(C, D).call()

    assert token_network.functions.channel_counter().call() == 0
    assert token_network.functions.participants_hash_to_channel_identifier(AB_hash).call() == 0
    assert token_network.functions.participants_hash_to_channel_identifier(BC_hash).call() == 0
    assert token_network.functions.participants_hash_to_channel_identifier(CD_hash).call() == 0
    assert token_network.functions.getChannelIdentifier(A, B).call() == 0

    # Create channel between A and B, counter increases
    create_channel(A, B)
    assert token_network.functions.channel_counter().call() == 1
    assert token_network.functions.participants_hash_to_channel_identifier(AB_hash).call() == 1
    assert token_network.functions.getChannelIdentifier(A, B).call() == 1

    # We still do not have a channel between B and C
    assert token_network.functions.getChannelIdentifier(B, C).call() == 0

    # Create channel between B and C, counter increases
    create_channel(B, C)
    assert token_network.functions.channel_counter().call() == 2
    assert token_network.functions.participants_hash_to_channel_identifier(BC_hash).call() == 2
    assert token_network.functions.getChannelIdentifier(B, C).call() == 2

    # We still do not have a channel between C and D
    assert token_network.functions.getChannelIdentifier(C, D).call() == 0

    # Create channel between C and D, counter increases
    create_channel(C, D)
    assert token_network.functions.channel_counter().call() == 3
    assert token_network.functions.participants_hash_to_channel_identifier(CD_hash).call() == 3
    assert token_network.functions.getChannelIdentifier(C, D).call() == 3


def test_state_channel_identifier_invalid(token_network, get_accounts, create_channel):
    """ getChannelInfo() returns the empty channel state for ont-too-big channelID """
    (A, B, C) = get_accounts(3)
    channel_id = 0

    pairs = permutations([A, B, C], 2)
    for pair in pairs:
        (settle_block_number, state) = token_network.functions.getChannelInfo(
            channel_id, *pair
        ).call()
        assert settle_block_number == 0
        assert state == ChannelState.NONEXISTENT

    for pair in pairs:
        create_channel(*pair)
        (settle_block_number, state) = token_network.functions.getChannelInfo(0, *pair).call()
        assert settle_block_number > 0
        assert state == ChannelState.OPENED

    current_counter = token_network.functions.channel_counter().call()

    for pair in pairs:
        (settle_block_number, state) = token_network.functions.getChannelInfo(
            current_counter + 1, *pair
        ).call()
        assert settle_block_number == 0
        assert state == ChannelState.NONEXISTENT


def test_open_channel_state(token_network, get_accounts):
    """ Observe the state of the channel after a openChannel() call """
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN + 10

    channel_counter = token_network.functions.channel_counter().call()
    participants_hash = token_network.functions.getParticipantsHash(A, B).call()

    assert (
        token_network.functions.participants_hash_to_channel_identifier(participants_hash).call()
        == 0
    )
    assert token_network.functions.getChannelIdentifier(A, B).call() == 0

    token_network.functions.openChannel(A, B, settle_timeout).call_and_transact()
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()

    assert token_network.functions.channel_counter().call() == channel_counter + 1
    assert (
        token_network.functions.participants_hash_to_channel_identifier(participants_hash).call()
        == channel_counter + 1
    )

    channel_info_response = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    settle_block_number = channel_info_response[ChannelInfoIndex.SETTLE_BLOCK]
    state = channel_info_response[ChannelInfoIndex.STATE]
    assert settle_block_number == settle_timeout
    assert state == ChannelState.OPENED

    response = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    A_deposit = response[ParticipantInfoIndex.DEPOSIT]
    A_withdrawn = response[ParticipantInfoIndex.WITHDRAWN]
    A_is_the_closer = response[ParticipantInfoIndex.IS_CLOSER]
    A_balance_hash = response[ParticipantInfoIndex.BALANCE_HASH]
    A_nonce = response[ParticipantInfoIndex.NONCE]
    A_locksroot = response[ParticipantInfoIndex.LOCKSROOT]
    A_locked_amount = response[ParticipantInfoIndex.LOCKED_AMOUNT]
    assert A_deposit == 0
    assert A_withdrawn == 0
    assert A_is_the_closer is False
    assert A_balance_hash == EMPTY_BALANCE_HASH
    assert A_nonce == 0
    assert A_locksroot == EMPTY_LOCKSROOT
    assert A_locked_amount == 0

    (
        B_deposit,
        B_withdrawn,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        B_locksroot,
        B_locked_amount,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_deposit == 0
    assert B_withdrawn == 0
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0
    assert B_locksroot == EMPTY_LOCKSROOT
    assert B_locked_amount == 0


def test_reopen_channel(web3, token_network, get_accounts):
    """ Open a second channel after settling one """
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    token_network.functions.openChannel(A, B, settle_timeout).call_and_transact()
    channel_identifier1 = token_network.functions.getChannelIdentifier(A, B).call()
    channel_counter1 = token_network.functions.participants_hash_to_channel_identifier(
        get_participants_hash(A, B)
    ).call()

    # Opening twice fails
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, settle_timeout).call()

    # Close channel
    token_network.functions.closeChannel(
        channel_identifier1, B, EMPTY_LOCKSROOT, 0, EMPTY_ADDITIONAL_HASH, EMPTY_SIGNATURE
    ).call_and_transact({"from": A})

    # Reopen Channel before settlement fails
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, settle_timeout).call()

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout + 1)

    # Settle channel
    token_network.functions.settleChannel(
        channel_identifier1, A, 0, 0, EMPTY_LOCKSROOT, B, 0, 0, EMPTY_LOCKSROOT
    ).call_and_transact({"from": A})

    # Reopening the channel should work iff channel is settled
    token_network.functions.openChannel(A, B, settle_timeout).call_and_transact()
    channel_identifier2 = token_network.functions.getChannelIdentifier(A, B).call()
    assert channel_identifier2 != channel_identifier1
    assert (
        token_network.functions.participants_hash_to_channel_identifier(
            get_participants_hash(A, B)
        ).call()
        == channel_counter1 + 1
    )

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier2, A, B
    ).call()
    assert settle_block_number == settle_timeout
    assert state == ChannelState.OPENED

    (
        A_deposit,
        A_withdrawn,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        A_locksroot,
        A_locked_amount,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier2, A, B).call()
    assert A_deposit == 0
    assert A_withdrawn == 0
    assert A_is_the_closer is False
    assert A_balance_hash == EMPTY_BALANCE_HASH
    assert A_nonce == 0
    assert A_locksroot == EMPTY_LOCKSROOT
    assert A_locked_amount == 0

    (
        B_deposit,
        B_withdrawn,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        B_locksroot,
        B_locked_amount,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier2, B, A).call()
    assert B_deposit == 0
    assert B_withdrawn == 0
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0
    assert B_locksroot == EMPTY_LOCKSROOT
    assert B_locked_amount == 0


def test_open_channel_event(get_accounts, token_network, event_handler):
    """ A successful openChannel() causes an OPENED event """
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    txn_hash = token_network.functions.openChannel(
        A, B, TEST_SETTLE_TIMEOUT_MIN
    ).call_and_transact()
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()

    ev_handler.add(
        txn_hash,
        ChannelEvent.OPENED,
        check_channel_opened(channel_identifier, A, B, TEST_SETTLE_TIMEOUT_MIN),
    )
    ev_handler.check()
