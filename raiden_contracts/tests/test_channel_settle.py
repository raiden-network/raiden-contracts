from copy import deepcopy
from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import (
    TEST_SETTLE_TIMEOUT_MIN,
    ChannelEvent,
    ChannelState,
    MessageTypeId,
)
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_BALANCE_HASH,
    EMPTY_SIGNATURE,
    LOCKSROOT_OF_NO_LOCKS,
    UINT256_MAX,
    ChannelValues,
    LockedAmounts,
    call_and_transact,
    fake_bytes,
    get_onchain_settlement_amounts,
    get_settlement_amounts,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.events import check_channel_settled
from raiden_contracts.utils.pending_transfers import (
    get_pending_transfers_tree_with_generated_lists,
)


def test_settle_no_bp_success(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ The simplest settlement without any balance proofs provided """
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 6
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)

    # Close channel with no balance proof
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    # Do not call updateNonClosingBalanceProof

    # Settlement window must be over before settling the channel
    mine_blocks(web3, settle_timeout + 1)

    # Settling the channel should work with no balance proofs
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier=channel_identifier,
            participant1=A,
            participant1_transferred_amount=0,
            participant1_locked_amount=0,
            participant1_locksroot=LOCKSROOT_OF_NO_LOCKS,
            participant2=B,
            participant2_transferred_amount=0,
            participant2_locked_amount=0,
            participant2_locksroot=LOCKSROOT_OF_NO_LOCKS,
        ),
        {"from": A},
    )

    assert custom_token.functions.balanceOf(A).call() == deposit_A
    assert custom_token.functions.balanceOf(B).call() == deposit_B


def test_settle_channel_state(
    web3: Web3,
    get_accounts: Callable,
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    close_and_update_channel: Callable,
    settle_state_tests: Callable,
) -> None:
    """ settleChannel() with some balance proofs """
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(
        deposit=40,
        withdrawn=10,
        transferred=20020,
        locked_amounts=LockedAmounts(claimable_locked=3, unclaimable_locked=4),
    )
    vals_B = ChannelValues(
        deposit=35,
        withdrawn=5,
        transferred=20030,
        locked_amounts=LockedAmounts(claimable_locked=2, unclaimable_locked=3),
    )

    pending_transfers_tree_A = get_pending_transfers_tree_with_generated_lists(
        web3,
        unlockable_amount=vals_A.locked_amounts.claimable_locked,
        expired_amount=vals_A.locked_amounts.unclaimable_locked,
    )
    pending_transfers_tree_B = get_pending_transfers_tree_with_generated_lists(
        web3,
        unlockable_amount=vals_B.locked_amounts.claimable_locked,
        expired_amount=vals_B.locked_amounts.unclaimable_locked,
    )
    vals_A.locksroot = pending_transfers_tree_A.hash_of_packed_transfers
    vals_B.locksroot = pending_transfers_tree_B.hash_of_packed_transfers

    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)
    withdraw_channel(channel_identifier, A, vals_A.withdrawn, UINT256_MAX, B)
    withdraw_channel(channel_identifier, B, vals_B.withdrawn, UINT256_MAX, A)
    close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)

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
    assert custom_token.functions.balanceOf(token_network.address).call() == post_balance_contract


def test_settle_single_direct_transfer_for_closing_party(
    web3: Web3,
    get_accounts: Callable,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """ Test settle of a channel with one direct transfer to the participant
    that called close.
    """
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=1, withdrawn=0, transferred=0),
        ChannelValues(deposit=10, withdrawn=0, transferred=5),
    )
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, vals_A.deposit, B)
    channel_deposit(channel_identifier, B, vals_B.deposit, A)

    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        vals_B.transferred,
        vals_B.locked_amounts.locked,
        1,
        LOCKSROOT_OF_NO_LOCKS,
    )
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    mine_blocks(web3, settle_timeout + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier=channel_identifier,
            participant1=A,
            participant1_transferred_amount=0,
            participant1_locked_amount=0,
            participant1_locksroot=LOCKSROOT_OF_NO_LOCKS,
            participant2=B,
            participant2_transferred_amount=vals_B.transferred,
            participant2_locked_amount=0,
            participant2_locksroot=LOCKSROOT_OF_NO_LOCKS,
        ),
        {"from": A},
    )

    # Calculate how much A and B should receive
    expected_settlement = get_settlement_amounts(vals_A, vals_B)
    # Calculate how much A and B receive according to onchain computation
    onchain_settlement = get_onchain_settlement_amounts(vals_A, vals_B)

    assert expected_settlement.participant1_balance == onchain_settlement.participant1_balance
    assert expected_settlement.participant2_balance == onchain_settlement.participant2_balance
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 6
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 5
    assert (
        custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract - 11
    )


def test_settle_single_direct_transfer_for_counterparty(
    web3: Web3,
    get_accounts: Callable,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ Test settle of a channel with one direct transfer to the participant
    that did not call close.
    """
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=10, withdrawn=0, transferred=5),
        ChannelValues(deposit=1, withdrawn=0, transferred=0),
    )
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, vals_A.deposit, B)
    channel_deposit(channel_identifier, B, vals_B.deposit, A)
    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    balance_proof_A = create_balance_proof(
        channel_identifier,
        A,
        vals_A.transferred,
        vals_A.locked_amounts.locked,
        1,
        LOCKSROOT_OF_NO_LOCKS,
    )

    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )
    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ),
        {"from": B},
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    mine_blocks(web3, settle_timeout + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier=channel_identifier,
            participant1=B,
            participant1_transferred_amount=0,
            participant1_locked_amount=0,
            participant1_locksroot=LOCKSROOT_OF_NO_LOCKS,
            participant2=A,
            participant2_transferred_amount=vals_A.transferred,
            participant2_locked_amount=0,
            participant2_locksroot=LOCKSROOT_OF_NO_LOCKS,
        ),
        {"from": B},
    )

    # Calculate how much A and B should receive
    expected_settlement = get_settlement_amounts(vals_B, vals_A)
    # Calculate how much A and B receive according to onchain computation
    onchain_settlement = get_onchain_settlement_amounts(vals_B, vals_A)

    assert expected_settlement.participant1_balance == onchain_settlement.participant1_balance
    assert expected_settlement.participant2_balance == onchain_settlement.participant2_balance
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 5
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 6
    assert (
        custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract - 11
    )


def test_settlement_with_unauthorized_token_transfer(
    web3: Web3,
    get_accounts: Callable,
    custom_token: Contract,
    token_network: Contract,
    assign_tokens: Callable,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    close_and_update_channel: Callable,
) -> None:
    """ A participant transfers some tokens to the contract and so loses them """
    externally_transferred_amount = 5
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = (
        ChannelValues(deposit=35, withdrawn=10, transferred=0),
        ChannelValues(deposit=40, withdrawn=10, transferred=0),
    )
    vals_A.locksroot = fake_bytes(32, "02")
    vals_B.locksroot = fake_bytes(32, "03")

    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

    withdraw_channel(channel_identifier, A, vals_A.withdrawn, UINT256_MAX, B)
    withdraw_channel(channel_identifier, B, vals_B.withdrawn, UINT256_MAX, A)

    close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)

    # Assign additional tokens to A
    assign_tokens(A, externally_transferred_amount)
    assert custom_token.functions.balanceOf(A).call() >= externally_transferred_amount

    # Fetch onchain balances after settlement
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # A does a transfer to the token_network without appropriate function call - tokens are lost
    call_and_transact(
        custom_token.functions.transfer(token_network.address, externally_transferred_amount),
        {"from": A},
    )
    assert custom_token.functions.balanceOf(token_network.address).call() == (
        pre_balance_contract + externally_transferred_amount
    )

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)

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
        pre_balance_A + settlement.participant1_balance - externally_transferred_amount
    ) == post_balance_A

    # B's settlement works correctly
    assert pre_balance_B + settlement.participant2_balance == post_balance_B

    # The externally_transferred_amount stays in the contract
    assert (
        pre_balance_contract
        - settlement.participant1_balance
        - settlement.participant2_balance
        + externally_transferred_amount
    ) == post_balance_contract


def test_settle_wrong_state_fail(
    web3: Web3,
    get_accounts: Callable,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_block: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ settleChannel() fails on OPENED state and on CLOSED state before the settlement block """
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(deposit=35)
    vals_B = ChannelValues(deposit=40)
    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

    (settle_timeout, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert state == ChannelState.OPENED
    assert settle_timeout == TEST_SETTLE_TIMEOUT_MIN

    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)
    txn_hash = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert state == ChannelState.CLOSED
    assert settle_block_number == TEST_SETTLE_TIMEOUT_MIN + get_block(txn_hash)
    assert web3.eth.blockNumber < settle_block_number

    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    assert web3.eth.blockNumber > settle_block_number

    # Channel is settled
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert state == ChannelState.REMOVED
    assert settle_block_number == 0


def test_settle_wrong_balance_hash(
    web3: Web3,
    get_accounts: Callable,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    close_and_update_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """ Calling settleChannel() with various wrong arguments and see failures """
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(
        deposit=35,
        withdrawn=0,
        transferred=5,
        locked_amounts=LockedAmounts(claimable_locked=10, unclaimable_locked=2),
    )
    vals_B = ChannelValues(
        deposit=40,
        withdrawn=0,
        transferred=15,
        locked_amounts=LockedAmounts(claimable_locked=5, unclaimable_locked=4),
    )
    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree_with_generated_lists(
        web3,
        unlockable_amount=vals_A.locked_amounts.claimable_locked,
        expired_amount=vals_A.locked_amounts.unclaimable_locked,
    )
    vals_A.locksroot = pending_transfers_tree_A.hash_of_packed_transfers
    # Reveal A's secrets.
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree_with_generated_lists(
        web3,
        unlockable_amount=vals_B.locked_amounts.claimable_locked,
        expired_amount=vals_B.locked_amounts.unclaimable_locked,
    )
    vals_B.locksroot = pending_transfers_tree_B.hash_of_packed_transfers
    # Reveal B's secrets
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)

    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_A, A, vals_B)

    vals_A_fail = deepcopy(vals_A)
    vals_A_fail.transferred += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.transferred = 0
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.transferred = UINT256_MAX
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_B, A, vals_A_fail)

    vals_A_fail = deepcopy(vals_A)
    vals_A_fail.locked_amounts.claimable_locked += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.locked_amounts.claimable_locked = 0
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.locked_amounts.unclaimable_locked = 0
    vals_A_fail.locked_amounts.claimable_locked = UINT256_MAX
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_B, A, vals_A_fail)

    vals_A_fail = deepcopy(vals_A)
    vals_A_fail.locksroot = LOCKSROOT_OF_NO_LOCKS
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_A_fail.locksroot = fake_bytes(32, "01")
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A_fail, B, vals_B)

    vals_B_fail = deepcopy(vals_B)
    vals_B_fail.transferred += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail.transferred = 0
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, B, vals_B_fail, A, vals_A)

    vals_B_fail.transferred = UINT256_MAX
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail = deepcopy(vals_B)
    vals_B_fail.locked_amounts.claimable_locked += 1
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail.locked_amounts.claimable_locked = 0
    with pytest.raises(AssertionError):
        call_settle(token_network, channel_identifier, B, vals_B_fail, A, vals_A)

    vals_B_fail.locked_amounts.unclaimable_locked = 0
    vals_B_fail.locked_amounts.claimable_locked = UINT256_MAX
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail = deepcopy(vals_B)
    vals_B_fail.locksroot = LOCKSROOT_OF_NO_LOCKS
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    vals_B_fail.locksroot = fake_bytes(32, "01")
    with pytest.raises(TransactionFailed):
        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B_fail)

    # Channel is settled
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)


def test_settle_channel_event(
    web3: Web3,
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    event_handler: Callable,
) -> None:
    """ A successful settleChannel() call causes a SETTLED event """
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 1, LOCKSROOT_OF_NO_LOCKS)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, LOCKSROOT_OF_NO_LOCKS)
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )
    close_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )

    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), close_sig_A
        ),
        {"from": A},
    )
    call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ),
        {"from": B},
    )

    mine_blocks(web3, settle_timeout + 1)
    txn_hash = call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier=channel_identifier,
            participant1=B,
            participant1_transferred_amount=5,
            participant1_locked_amount=0,
            participant1_locksroot=LOCKSROOT_OF_NO_LOCKS,
            participant2=A,
            participant2_transferred_amount=10,
            participant2_locked_amount=0,
            participant2_locksroot=LOCKSROOT_OF_NO_LOCKS,
        ),
        {"from": A},
    )

    ev_handler.add(txn_hash, ChannelEvent.SETTLED, check_channel_settled(channel_identifier, 5, 5))
    ev_handler.check()
