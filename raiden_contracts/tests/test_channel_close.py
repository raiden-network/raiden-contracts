import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import (
    TEST_SETTLE_TIMEOUT_MIN,
    ChannelEvent,
    ChannelState,
)
from raiden_contracts.utils.events import check_channel_closed
from raiden_contracts.tests.utils import ChannelValues
from raiden_contracts.tests.fixtures.config import (
    EMPTY_BALANCE_HASH,
    EMPTY_LOCKSROOT,
    EMPTY_ADDITIONAL_HASH,
    EMPTY_SIGNATURE,
    fake_bytes,
)


def test_close_nonexistent_channel(
        token_network,
        get_accounts,
):
    (A, B) = get_accounts(2)
    non_existent_channel_identifier = 1

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        non_existent_channel_identifier,
        A,
        B,
    ).call()
    assert state == ChannelState.NONEXISTENT
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            non_existent_channel_identifier,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
        ).transact({'from': A})


def test_close_settled_channel_fail(
        web3,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B, TEST_SETTLE_TIMEOUT_MIN)[0]
    channel_deposit(channel_identifier, A, 5, B)

    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.OPENED

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).transact({'from': A})
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)
    token_network.functions.settleChannel(
        channel_identifier,
        A,
        0,
        0,
        EMPTY_LOCKSROOT,
        B,
        0,
        0,
        EMPTY_LOCKSROOT,
    ).transact({'from': A})

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.REMOVED
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
        ).transact({'from': A})


def test_close_wrong_signature(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 6
    transferred_amount = 5
    nonce = 3
    locksroot = fake_bytes(32, '03')

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier,
        C,
        transferred_amount,
        0,
        nonce,
        locksroot,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            *balance_proof,
        ).transact({'from': A})


def test_close_call_twice_fail(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 5, B)

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
        ).transact({'from': A})


def test_close_wrong_sender(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
):
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 5, B)

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
        ).transact({'from': C})


def test_close_nonce_zero(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof,
):
    (A, B) = get_accounts(2)
    vals_B = ChannelValues(
        deposit=20,
        transferred=5,
        locksroot=fake_bytes(32, '03'),
        claimable_locked=3,
        unclaimable_locked=4,
        nonce=0,
    )
    # Create channel and deposit
    channel_identifier = create_channel(A, B)[0]

    # Create balance proofs
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        vals_B.transferred,
        vals_B.locked,
        vals_B.nonce,
        vals_B.locksroot,
    )

    (
        _, _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).transact({'from': A})

    # Even though we somehow provide valid values for the balance proof, they are not taken into
    # consideration if the nonce is 0.
    # The Raiden client enforces that the nonce is > 0 if off-chain transfers are made.
    (
        _, _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0


def test_close_first_argument_is_for_partner_transfer(
        token_network,
        create_channel,
        get_accounts,
        create_balance_proof,
):
    (A, B) = get_accounts(2)

    # Create channel
    channel_identifier = create_channel(A, B, settle_timeout=TEST_SETTLE_TIMEOUT_MIN)[0]

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier,
        B,
    )

    # closeChannel fails, if the provided balance proof is from the same participant who closes
    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            *balance_proof,
        ).transact({'from': B})

    # Else, closeChannel works with this balance proof
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof,
    ).transact({'from': A})


def test_close_first_participant_can_close(
        token_network,
        create_channel,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).transact({'from': A})


def test_close_second_participant_can_close(
        token_network,
        create_channel,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    token_network.functions.closeChannel(
        channel_identifier,
        A,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).transact({'from': B})


def test_close_channel_state(
        web3,
        custom_token,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        get_block,
        create_balance_proof,
        txn_cost,
):
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    vals_B = ChannelValues(
        deposit=20,
        transferred=5,
        locksroot=fake_bytes(32, '03'),
        claimable_locked=3,
        unclaimable_locked=4,
        nonce=3,
    )

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, B, vals_B.deposit, A)

    # Create balance proofs
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        vals_B.transferred,
        vals_B.locked,
        vals_B.nonce,
        vals_B.locksroot,
    )

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert settle_block_number == settle_timeout
    assert state == ChannelState.OPENED

    (
        _,
        _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert A_is_the_closer is False
    assert A_balance_hash == EMPTY_BALANCE_HASH
    assert A_nonce == 0
    (
        _, _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0

    pre_eth_balance_A = web3.eth.getBalance(A)
    pre_eth_balance_B = web3.eth.getBalance(B)
    pre_eth_balance_contract = web3.eth.getBalance(token_network.address)
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).transact({'from': A})

    # Test that no balances have changed.
    # There are no transfers to be made in closeChannel.
    assert web3.eth.getBalance(A) == pre_eth_balance_A - txn_cost(txn_hash)
    assert web3.eth.getBalance(B) == pre_eth_balance_B
    assert web3.eth.getBalance(token_network.address) == pre_eth_balance_contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert settle_block_number == settle_timeout + get_block(txn_hash)
    assert state == ChannelState.CLOSED

    (
        _, _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert A_is_the_closer is True
    assert A_balance_hash == EMPTY_BALANCE_HASH
    assert A_nonce == 0

    (
        _, _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == balance_proof_B[0]
    assert B_nonce == vals_B.nonce


def test_close_channel_event_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        event_handler,
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)[0]

    # No off-chain transfers have occured
    # There is no signature data here, because it was never provided to A
    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).transact({'from': A})

    ev_handler.add(txn_hash, ChannelEvent.CLOSED, check_channel_closed(channel_identifier, A, 0))
    ev_handler.check()


def test_close_replay_reopened_channel(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
):
    (A, B) = get_accounts(2)
    nonce = 3
    values_A = ChannelValues(
        deposit=10,
        transferred=0,
        locked=0,
        locksroot=EMPTY_LOCKSROOT,
    )
    values_B = ChannelValues(
        deposit=20,
        transferred=15,
        locked=0,
        locksroot=EMPTY_LOCKSROOT,
    )
    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, B, values_B.deposit, A)

    balance_proof_B = create_balance_proof(
        channel_identifier1,
        B,
        values_B.transferred,
        values_B.locked,
        nonce,
        values_B.locksroot,
    )
    token_network.functions.closeChannel(
        channel_identifier1,
        B,
        *balance_proof_B,
    ).transact({'from': A})
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)
    token_network.functions.settleChannel(
        channel_identifier1,
        A,
        values_A.transferred,
        values_A.locked,
        values_A.locksroot,
        B,
        values_B.transferred,
        values_B.locked,
        values_B.locksroot,
    ).transact({'from': A})

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, B, values_B.deposit, A)

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier2,
            B,
            *balance_proof_B,
        ).transact({'from': A})

    # Balance proof with correct channel_identifier must work
    balance_proof_B2 = create_balance_proof(
        channel_identifier2,
        B,
        values_B.transferred,
        values_B.locked,
        nonce,
        values_B.locksroot,
    )
    token_network.functions.closeChannel(
        channel_identifier2,
        B,
        *balance_proof_B2,
    ).transact({'from': A})


def test_close_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        event_handler,
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof = create_balance_proof(
        channel_identifier,
        B,
        transferred_amount=5,
        locked_amount=0,
        nonce=3,
    )

    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof,
    ).transact({'from': A})

    ev_handler.add(txn_hash, ChannelEvent.CLOSED, check_channel_closed(channel_identifier, A, 3))
    ev_handler.check()
