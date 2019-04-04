from copy import deepcopy

import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ChannelEvent, ChannelState
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_BALANCE_HASH,
    EMPTY_LOCKSROOT,
    EMPTY_SIGNATURE,
    MAX_UINT256,
    ChannelValues,
    fake_bytes,
    get_onchain_settlement_amounts,
    get_settlement_amounts,
)
from raiden_contracts.utils import get_pending_transfers_tree
from raiden_contracts.utils.events import check_channel_settled


def test_settle_no_bp_success(
        web3,
        custom_token,
        token_network,
        create_channel_and_deposit,
        get_accounts,
):
    """ The simplest settlement without any balance proofs provided """
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 6
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    # Close channel with no balance proof
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    # Do not call updateNonClosingBalanceProof

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout + 1)

    # Settling the channel should work with no balance proofs
    token_network.functions.settleChannel(
        channel_identifier=channel_identifier,
        participant1=A,
        participant1_transferred_amount=0,
        participant1_locked_amount=0,
        participant1_locksroot=EMPTY_LOCKSROOT,
        participant2=B,
        participant2_transferred_amount=0,
        participant2_locked_amount=0,
        participant2_locksroot=EMPTY_LOCKSROOT,
    ).call_and_transact({'from': A})

    assert custom_token.functions.balanceOf(A).call() == deposit_A
    assert custom_token.functions.balanceOf(B).call() == deposit_B


def test_settle_channel_state(
        web3,
        get_accounts,
        custom_token,
        token_network,
        create_channel_and_deposit,
        withdraw_channel,
        close_and_update_channel,
        settle_state_tests,
):
    """ settleChannel() with some balance proofs """
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(
        deposit=40,
        withdrawn=10,
        transferred=20020,
        claimable_locked=3,
        unclaimable_locked=4,
    )
    vals_B = ChannelValues(
        deposit=35,
        withdrawn=5,
        transferred=20030,
        claimable_locked=2,
        unclaimable_locked=3,
    )

    pending_transfers_tree_A = get_pending_transfers_tree(
        web3,
        unlockable_amount=vals_A.claimable_locked,
        expired_amount=vals_A.unclaimable_locked,
    )
    pending_transfers_tree_B = get_pending_transfers_tree(
        web3,
        unlockable_amount=vals_B.claimable_locked,
        expired_amount=vals_B.unclaimable_locked,
    )
    vals_A.locksroot = pending_transfers_tree_A.merkle_root
    vals_B.locksroot = pending_transfers_tree_B.merkle_root

    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)
    withdraw_channel(channel_identifier, A, vals_A.withdrawn, B)
    withdraw_channel(channel_identifier, B, vals_B.withdrawn, A)
    close_and_update_channel(
        channel_identifier,
        A,
        vals_A,
        B,
        vals_B,
    )

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    # Balance & state tests
    settle_state_tests(
        channel_identifier,
        A,
        vals_A,
        B,
        vals_B,
        pre_balance_A,
        pre_balance_B,
        pre_balance_contract,
    )

    # Some manual checks for the final balances, in case the settlement algorithms
    # used in `settle_state_tests` are incorrect

    # FIXME after setTotalWithdraw is implemented again
    post_balance_A = pre_balance_A + 33
    post_balance_B = pre_balance_B + 15
    post_balance_contract = pre_balance_contract - 48

    assert custom_token.functions.balanceOf(A).call() == post_balance_A
    assert custom_token.functions.balanceOf(B).call() == post_balance_B
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == post_balance_contract


def test_settle_single_direct_transfer_for_closing_party(
        web3,
        get_accounts,
        custom_token,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
):
    """ Test settle of a channel with one direct transfer to the participant
    that called close.
    """
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=1, withdrawn=0, transferred=0, locked=0),
        ChannelValues(deposit=10, withdrawn=0, transferred=5, locked=0),
    )
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, vals_A.deposit, B)
    channel_deposit(channel_identifier, B, vals_B.deposit, A)

    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        vals_B.transferred,
        vals_B.locked,
        1,
        EMPTY_LOCKSROOT,
    )
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).call_and_transact({'from': A})

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    web3.testing.mine(settle_timeout + 1)
    token_network.functions.settleChannel(
        channel_identifier=channel_identifier,
        participant1=A,
        participant1_transferred_amount=0,
        participant1_locked_amount=0,
        participant1_locksroot=EMPTY_LOCKSROOT,
        participant2=B,
        participant2_transferred_amount=vals_B.transferred,
        participant2_locked_amount=0,
        participant2_locksroot=EMPTY_LOCKSROOT,
    ).call_and_transact({'from': A})

    # Calculate how much A and B should receive
    expected_settlement = get_settlement_amounts(vals_A, vals_B)
    # Calculate how much A and B receive according to onchain computation
    onchain_settlement = get_onchain_settlement_amounts(vals_A, vals_B)

    assert (expected_settlement.participant1_balance == onchain_settlement.participant1_balance)
    assert (expected_settlement.participant2_balance == onchain_settlement.participant2_balance)
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 6
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 5
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 11


def test_settle_single_direct_transfer_for_counterparty(
        web3,
        get_accounts,
        custom_token,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ Test settle of a channel with one direct transfer to the participant
    that did not call close.
    """
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=10, withdrawn=0, transferred=5, locked=0),
        ChannelValues(deposit=1, withdrawn=0, transferred=0, locked=0),
    )
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, vals_A.deposit, B)
    channel_deposit(channel_identifier, B, vals_B.deposit, A)
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_LOCKSROOT,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    balance_proof_A = create_balance_proof(
        channel_identifier,
        A,
        vals_A.transferred,
        vals_A.locked,
        1,
        EMPTY_LOCKSROOT,
    )

    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )
    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': B})

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    web3.testing.mine(settle_timeout + 1)
    token_network.functions.settleChannel(
        channel_identifier=channel_identifier,
        participant1=B,
        participant1_transferred_amount=0,
        participant1_locked_amount=0,
        participant1_locksroot=EMPTY_LOCKSROOT,
        participant2=A,
        participant2_transferred_amount=vals_A.transferred,
        participant2_locked_amount=0,
        participant2_locksroot=EMPTY_LOCKSROOT,
    ).call_and_transact({'from': B})

    # Calculate how much A and B should receive
    expected_settlement = get_settlement_amounts(vals_B, vals_A)
    # Calculate how much A and B receive according to onchain computation
    onchain_settlement = get_onchain_settlement_amounts(vals_B, vals_A)

    assert (expected_settlement.participant1_balance == onchain_settlement.participant1_balance)
    assert (expected_settlement.participant2_balance == onchain_settlement.participant2_balance)
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 5
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 6
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 11


def test_settlement_with_unauthorized_token_transfer(
        web3,
        get_accounts,
        custom_token,
        token_network,
        assign_tokens,
        create_channel_and_deposit,
        withdraw_channel,
        close_and_update_channel,
):
    """ A participant transfers some tokens to the contract and so loses them """
    externally_transferred_amount = 5
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=35, withdrawn=10, transferred=0, locked=0),
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=0),
    )
    vals_A.locksroot = fake_bytes(32, '02')
    vals_B.locksroot = fake_bytes(32, '03')

    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

    withdraw_channel(channel_identifier, A, vals_A.withdrawn, B)
    withdraw_channel(channel_identifier, B, vals_B.withdrawn, A)

    close_and_update_channel(
        channel_identifier,
        A,
        vals_A,
        B,
        vals_B,
    )

    # Assign additional tokens to A
    assign_tokens(A, externally_transferred_amount)
    assert custom_token.functions.balanceOf(A).call() >= externally_transferred_amount

    # Fetch onchain balances after settlement
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # A does a transfer to the token_network without appropriate function call - tokens are lost
    custom_token.functions.transfer(
        token_network.address,
        externally_transferred_amount,
    ).call_and_transact({'from': A})
    assert custom_token.functions.balanceOf(token_network.address).call() == (
        pre_balance_contract +
        externally_transferred_amount
    )

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)

    # Compute expected settlement amounts
    settlement = get_settlement_amounts(vals_A, vals_B)

    # Channel is settled
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    # Fetch onchain balances after settlement
    post_balance_A = custom_token.functions.balanceOf(A).call()
    post_balance_B = custom_token.functions.balanceOf(B).call()
    post_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # A has lost the externally_transferred_amount
    assert (
        pre_balance_A +
        settlement.participant1_balance -
        externally_transferred_amount
    ) == post_balance_A

    # B's settlement works correctly
    assert pre_balance_B + settlement.participant2_balance == post_balance_B

    # The externally_transferred_amount stays in the contract
    assert (
        pre_balance_contract -
        settlement.participant1_balance -
        settlement.participant2_balance +
        externally_transferred_amount
    ) == post_balance_contract


def test_settle_wrong_state_fail(
        web3,
        get_accounts,
        token_network,
        create_channel_and_deposit,
        get_block,
):
    """ settleChannel() fails on OPENED state and on CLOSED state before the settlement block """
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(deposit=35)
    vals_B = ChannelValues(deposit=40)
    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

    (settle_timeout, state) = token_network.functions.getChannelInfo(
        channel_identifier,
        A,
        B,
    ).call()
    assert state == ChannelState.OPENED
    assert settle_timeout == TEST_SETTLE_TIMEOUT_MIN

    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        EMPTY_BALANCE_HASH,
        0,
        EMPTY_ADDITIONAL_HASH,
        EMPTY_SIGNATURE,
    ).call_and_transact({'from': A})

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier,
        A,
        B,
    ).call()
    assert state == ChannelState.CLOSED
    assert settle_block_number == TEST_SETTLE_TIMEOUT_MIN + get_block(txn_hash)
    assert web3.eth.blockNumber < settle_block_number

    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)
    assert web3.eth.blockNumber > settle_block_number

    # Channel is settled
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier,
        A,
        B,
    ).call()
    assert state == ChannelState.REMOVED
    assert settle_block_number == 0


def test_settle_wrong_balance_hash(
        web3,
        get_accounts,
        token_network,
        create_channel_and_deposit,
        close_and_update_channel,
        get_block,
        reveal_secrets,
):
    """ Calling settleChannel() with various wrong arguments and see failures """
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(
        deposit=35,
        withdrawn=0,
        transferred=5,
        claimable_locked=10,
        unclaimable_locked=2,
    )
    vals_B = ChannelValues(
        deposit=40,
        withdrawn=0,
        transferred=15,
        claimable_locked=5,
        unclaimable_locked=4,
    )
    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(
        web3,
        unlockable_amount=vals_A.claimable_locked,
        expired_amount=vals_A.unclaimable_locked,
    )
    vals_A.locksroot = pending_transfers_tree_A.merkle_root
    # Reveal A's secrets.
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(
        web3,
        unlockable_amount=vals_B.claimable_locked,
        expired_amount=vals_B.unclaimable_locked,
    )
    vals_B.locksroot = pending_transfers_tree_B.merkle_root
    # Reveal B's secrets
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    close_and_update_channel(
        channel_identifier,
        A,
        vals_A,
        B,
        vals_B,
    )

    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)

    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_A, A, vals_B)

    vals_A_fail = deepcopy(vals_A)
    vals_A_fail.transferred += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.transferred = 0
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.transferred = MAX_UINT256
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_B, A, vals_A_fail)

    vals_A_fail = deepcopy(vals_A)
    vals_A_fail.locked += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.locked = 0
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.locked = MAX_UINT256
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_B, A, vals_A_fail)

    vals_A_fail = deepcopy(vals_A)
    vals_A_fail.locksroot = EMPTY_LOCKSROOT
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.locksroot = fake_bytes(32, '01')
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_B_fail = deepcopy(vals_B)
    vals_B_fail.transferred += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail.transferred = 0
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_B_fail, A, vals_A)

    vals_B_fail.transferred = MAX_UINT256
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail = deepcopy(vals_B)
    vals_B_fail.locked += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail.locked = 0
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_B_fail, A, vals_A)

    vals_B_fail.locked = MAX_UINT256
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail = deepcopy(vals_B)
    vals_B_fail.locksroot = EMPTY_LOCKSROOT
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail.locksroot = fake_bytes(32, '01')
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    # Channel is settled
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)


def test_settle_channel_event(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
        event_handler,
):
    """ A successful settleChannel() call causes a SETTLED event """
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 1, EMPTY_LOCKSROOT)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, EMPTY_LOCKSROOT)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).call_and_transact({'from': A})
    token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': B})

    web3.testing.mine(settle_timeout + 1)
    txn_hash = token_network.functions.settleChannel(
        channel_identifier=channel_identifier,
        participant1=B,
        participant1_transferred_amount=5,
        participant1_locked_amount=0,
        participant1_locksroot=EMPTY_LOCKSROOT,
        participant2=A,
        participant2_transferred_amount=10,
        participant2_locked_amount=0,
        participant2_locksroot=EMPTY_LOCKSROOT,
    ).call_and_transact({'from': A})

    ev_handler.add(txn_hash, ChannelEvent.SETTLED, check_channel_settled(
        channel_identifier,
        5,
        5,
    ))
    ev_handler.check()
