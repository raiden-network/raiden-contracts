from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ChannelEvent, ParticipantInfoIndex
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.utils import (
    LOCKSROOT_OF_NO_LOCKS,
    NONEXISTENT_LOCKSROOT,
    UINT256_MAX,
    ChannelValues,
    LockedAmounts,
    LockIndex,
    call_and_transact,
    fake_bytes,
    get_unlocked_amount,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.events import check_channel_unlocked
from raiden_contracts.utils.pending_transfers import (
    get_locked_amount,
    get_packed_transfers,
    get_pending_transfers_tree,
    random_secret,
)

# Account names like 'A', 'B', 'C' are intuitive here.
# pytest: disable=C0103


def test_packed_transfer_0_items(token_network_test_utils: Contract) -> None:
    """getHashAndUnlockedAmount() returns a reasonable return value for no items"""
    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getHashAndUnlockedAmountPublic(b"").call()
    assert locksroot == LOCKSROOT_OF_NO_LOCKS
    assert unlocked_amount == 0


def test_0_item_unlockable(web3: Web3, token_network_test_utils: Contract) -> None:
    """Test getHashRootAndUnlockedAmount() on zero items whose secret has been registered"""
    pending_transfers_tree = get_pending_transfers_tree(
        web3=web3, unlockable_amounts=[], expired_amounts=[]
    )

    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getHashAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()

    total_hash = pending_transfers_tree.hash_of_packed_transfers
    assert locksroot == total_hash
    assert unlocked_amount == 0


def test_1_item_unlockable(
    web3: Web3,
    get_accounts: Callable,
    token_network_test_utils: Contract,
    secret_registry_contract: Contract,
) -> None:
    """Test getHashRootAndUnlockedAmount() on a single item whose secret has been registered"""
    A = get_accounts(1)[0]
    pending_transfers_tree = get_pending_transfers_tree(
        web3=web3, unlockable_amounts=[6], expired_amounts=[]
    )

    call_and_transact(
        secret_registry_contract.functions.registerSecret(
            pending_transfers_tree.unlockable[0][LockIndex.SECRET]
        ),
        {"from": A},
    )
    assert (
        secret_registry_contract.functions.getSecretRevealBlockHeight(
            pending_transfers_tree.unlockable[0][LockIndex.SECRETHASH]
        ).call()
        == web3.eth.block_number
    )

    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getHashAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()

    total_hash = pending_transfers_tree.hash_of_packed_transfers
    assert locksroot == total_hash
    assert unlocked_amount == 6


def test_get_hash_length_fail(
    web3: Web3,
    get_accounts: Callable,
    token_network_test_utils: Contract,
    secret_registry_contract: Contract,
) -> None:
    """Test getHashAndUnlockedAmount() on inputs of irregular lengths"""
    network_utils = token_network_test_utils
    A = get_accounts(1)[0]
    pending_transfers_tree = get_pending_transfers_tree(web3, [2, 3, 6], [5])

    call_and_transact(
        secret_registry_contract.functions.registerSecret(
            pending_transfers_tree.unlockable[0][LockIndex.SECRET]
        ),
        {"from": A},
    )
    assert (
        secret_registry_contract.functions.getSecretRevealBlockHeight(
            pending_transfers_tree.unlockable[0][LockIndex.SECRETHASH]
        ).call()
        == web3.eth.block_number
    )

    packed = pending_transfers_tree.packed_transfers

    # packed length must be a multiple of 96
    with pytest.raises(TransactionFailed, match="TN: invalid locks size"):
        network_utils.functions.getHashAndUnlockedAmountPublic(packed[0:-1]).call()
    # last lock only contains expiration + locked_amount
    with pytest.raises(TransactionFailed, match="TN: invalid locks size"):
        network_utils.functions.getHashAndUnlockedAmountPublic(packed[0:-32]).call()
    # last lock only contains expiration
    with pytest.raises(TransactionFailed, match="TN: invalid locks size"):
        network_utils.functions.getHashAndUnlockedAmountPublic(packed[0:-64]).call()

    assert len(packed) % 96 == 0
    network_utils.functions.getHashAndUnlockedAmountPublic(packed).call()
    network_utils.functions.getHashAndUnlockedAmountPublic(packed[0:-96]).call()


def test_odd_even_components(
    web3: Web3,
    get_accounts: Callable,
    token_network_test_utils: Contract,
    reveal_secrets: Callable,
) -> None:
    """Test getHashAndUnlockedAmount() on an odd/even number of locks"""
    A = get_accounts(1)[0]

    # Even number of locks
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8, 3])
    reveal_secrets(A, pending_transfers_tree.unlockable)

    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getHashAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()
    total_hash = pending_transfers_tree.hash_of_packed_transfers

    assert locksroot == total_hash
    assert unlocked_amount == 9

    # Odd number of locks
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8])
    reveal_secrets(A, pending_transfers_tree.unlockable)

    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getHashAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()
    total_hash = pending_transfers_tree.hash_of_packed_transfers

    assert locksroot == total_hash
    assert unlocked_amount == 9


def test_locks_order(
    web3: Web3,
    get_accounts: Callable,
    token_network_test_utils: Contract,
    reveal_secrets: Callable,
    token_network: Contract,
    create_settled_channel: Callable,
) -> None:
    """Shuffling the leaves usually changes the root, but sometimes not"""
    network_utils = token_network_test_utils
    (A, B) = get_accounts(2)
    types = ["uint256", "uint256", "bytes32"]

    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8, 3])
    reveal_secrets(A, pending_transfers_tree.unlockable)

    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree.locked_amount,
        pending_transfers_tree.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
    )

    # Pending locks are in the insertion order.
    # If we change the order, we change the computed hash.
    wrong_order = pending_transfers_tree.transfers
    wrong_order[1], wrong_order[0] = wrong_order[0], wrong_order[1]
    wrong_order_packed = get_packed_transfers(wrong_order, types)
    (
        locksroot,
        unlocked_amount,
    ) = network_utils.functions.getHashAndUnlockedAmountPublic(wrong_order_packed).call()
    # If we change the order, we change the computed hash.
    assert locksroot != pending_transfers_tree.hash_of_packed_transfers
    assert unlocked_amount == 9
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(channel_identifier, B, A, wrong_order_packed).call()

    wrong_order = pending_transfers_tree.transfers
    wrong_order[2], wrong_order[0] = wrong_order[0], wrong_order[2]
    wrong_order_packed = get_packed_transfers(wrong_order, types)
    (
        locksroot,
        unlocked_amount,
    ) = network_utils.functions.getHashAndUnlockedAmountPublic(wrong_order_packed).call()
    assert locksroot != pending_transfers_tree.hash_of_packed_transfers
    assert unlocked_amount == 9
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(channel_identifier, B, A, wrong_order_packed).call()

    wrong_order = pending_transfers_tree.transfers
    wrong_order[0], wrong_order[-1] = wrong_order[-1], wrong_order[0]
    wrong_order_packed = get_packed_transfers(wrong_order, types)
    (
        locksroot,
        unlocked_amount,
    ) = network_utils.functions.getHashAndUnlockedAmountPublic(wrong_order_packed).call()
    assert locksroot != pending_transfers_tree.hash_of_packed_transfers
    assert unlocked_amount == 9
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(channel_identifier, B, A, wrong_order_packed).call()

    (locksroot, unlocked_amount,) = network_utils.functions.getHashAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()
    assert locksroot == pending_transfers_tree.hash_of_packed_transfers
    assert unlocked_amount == 9
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree.packed_transfers
        )
    )


def test_lock_data_from_packed_locks(
    web3: Web3,
    get_accounts: Callable,
    token_network_test_utils: Contract,
    secret_registry_contract: Contract,
    reveal_secrets: Callable,
) -> None:
    """Test getLockDataFromLockPublic() on various offsets"""
    network_utils = token_network_test_utils
    A = get_accounts(1)[0]

    unlockable_amounts = [3, 5]
    expired_amounts = [2, 8, 7]
    pending_transfers_tree = get_pending_transfers_tree(
        web3, unlockable_amounts, expired_amounts, max_expiration_delta=5
    )
    reveal_secrets(A, pending_transfers_tree.unlockable)

    def claimable(index: int) -> int:
        amount = pending_transfers_tree.transfers[index][1]
        return amount if amount in unlockable_amounts else 0

    # Lock data is ordered lexicographically, regardless of expiration status
    claimable_amount = network_utils.functions.getLockedAmountFromLockPublic(
        pending_transfers_tree.packed_transfers, 32
    ).call()
    assert claimable_amount == claimable(0)

    claimable_amount = network_utils.functions.getLockedAmountFromLockPublic(
        pending_transfers_tree.packed_transfers, 32 + 96
    ).call()
    assert claimable_amount == claimable(1)

    claimable_amount = network_utils.functions.getLockedAmountFromLockPublic(
        pending_transfers_tree.packed_transfers, 32 + 2 * 96
    ).call()
    assert claimable_amount == claimable(2)

    claimable_amount = network_utils.functions.getLockedAmountFromLockPublic(
        pending_transfers_tree.packed_transfers, 32 + 3 * 96
    ).call()
    assert claimable_amount == claimable(3)

    claimable_amount = network_utils.functions.getLockedAmountFromLockPublic(
        pending_transfers_tree.packed_transfers, 32 + 4 * 96
    ).call()
    assert claimable_amount == claimable(4)

    # Register last secret after expiration
    mine_blocks(web3, 5)
    last_lock = pending_transfers_tree.expired[-1]
    # expiration
    assert web3.eth.block_number > last_lock[0]
    # register secret
    call_and_transact(secret_registry_contract.functions.registerSecret(last_lock[3]))
    # ensure registration was done
    assert (
        secret_registry_contract.functions.getSecretRevealBlockHeight(last_lock[2]).call()
        == web3.eth.block_number
    )

    # Check that last secret is still regarded as expired
    claimable_amount = network_utils.functions.getLockedAmountFromLockPublic(
        pending_transfers_tree.packed_transfers, 32 + 4 * 96
    ).call()
    assert claimable_amount == claimable(4)

    # If the offset is bigger than the length of the packed locks, return (0, 0)
    claimable_amount = network_utils.functions.getLockedAmountFromLockPublic(
        pending_transfers_tree.packed_transfers, 32 + 5 * 96
    ).call()
    assert claimable_amount == 0


def test_unlock_wrong_locksroot(
    web3: Web3, token_network: Contract, create_settled_channel: Callable, get_accounts: Callable
) -> None:
    """Test unlocking with wrong pending locks"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [], settle_timeout)
    pending_transfers_tree_A_fake = get_pending_transfers_tree(web3, [1, 3, 6], [], settle_timeout)

    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount,
        pending_transfers_tree_A.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A_fake.packed_transfers
        ).call()

    # Fails for an empty packed locks
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(channel_identifier, B, A, b"").call()

    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        )
    )


def test_channel_unlock_bigger_locked_amount(
    web3: Web3,
    token_network: Contract,
    custom_token: Contract,
    secret_registry_contract: Contract,
    create_settled_channel: Callable,
    get_accounts: Callable,
    reveal_secrets: Callable,
) -> None:
    """Test an unlock() call that claims too little tokens"

    When an unlock() call does not contain enough pending locks to claim
    the locked amount declared in the settleChannel() call, the difference goes
    to the other party.
    """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    unlocked_amount = get_unlocked_amount(
        secret_registry_contract, pending_transfers_tree_A.packed_transfers
    )

    # We settle the channel with a bigger locked amount than we will need for the
    # actual pending transfers
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount + 1,
        pending_transfers_tree_A.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == pending_transfers_tree_A.locked_amount + 1

    # This should pass, even though the locked amount in storage is bigger. The rest of the
    # tokens is sent to A, as tokens corresponding to the locks that could not be unlocked.
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        )
    )
    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == (
        pre_balance_A + pending_transfers_tree_A.locked_amount - unlocked_amount + 1
    )
    assert balance_B == pre_balance_B + unlocked_amount
    assert balance_contract == 0


def test_channel_unlock_smaller_locked_amount(
    web3: Web3,
    token_network: Contract,
    custom_token: Contract,
    secret_registry_contract: Contract,
    create_settled_channel: Callable,
    get_accounts: Callable,
    reveal_secrets: Callable,
) -> None:
    """Test an unlock() call that claims too many tokens

    When settleChannel() call computes a smaller amount of locked tokens than
    the following unlock() call, the settleChannel() computation is stronger and
    the participant receives less tokens. Stealing tokens from other channels
    is then prevented."""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    unlocked_amount = get_unlocked_amount(
        secret_registry_contract, pending_transfers_tree_A.packed_transfers
    )

    # We settle the channel with a smaller locked amount than we will need for the
    # actual pending transfers
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount - 1,
        pending_transfers_tree_A.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == pending_transfers_tree_A.locked_amount - 1

    # This should pass, even though the locked amount in storage is smaller.
    # B will receive less tokens.
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        )
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == (
        pre_balance_A + pending_transfers_tree_A.locked_amount - unlocked_amount - 1
    )
    assert balance_B == pre_balance_B + unlocked_amount
    assert balance_contract == 0


def test_channel_unlock_bigger_unlocked_amount(
    web3: Web3,
    token_network: Contract,
    custom_token: Contract,
    secret_registry_contract: Contract,
    create_settled_channel: Callable,
    get_accounts: Callable,
    reveal_secrets: Callable,
) -> None:
    """unlock() transfers not more than the locked amount for more expensive unlock() demands"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    unlocked_amount = get_unlocked_amount(
        secret_registry_contract, pending_transfers_tree_A.packed_transfers
    )
    assert unlocked_amount < pending_transfers_tree_A.locked_amount

    # We settle the channel with a smaller locked amount than the amount that can be unlocked
    channel_identifier = create_settled_channel(
        A,
        unlocked_amount - 1,
        pending_transfers_tree_A.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == unlocked_amount - 1

    # This should pass, even though the locked amount in storage is smaller.
    # B will receive the entire locked amount, corresponding to the locks that have been unlocked
    # and A will receive nothing.
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        )
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A
    assert balance_B == pre_balance_B + unlocked_amount - 1
    assert balance_contract == 0


def test_channel_unlock_no_locked_amount_fail(
    web3: Web3,
    token_network: Contract,
    create_settled_channel: Callable,
    get_accounts: Callable,
    reveal_secrets: Callable,
) -> None:
    """After settleChannel() is called with zero locked amount, unlock() calls fail"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [2, 5], [4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    channel_identifier = create_settled_channel(
        A, 0, LOCKSROOT_OF_NO_LOCKS, B, 0, LOCKSROOT_OF_NO_LOCKS, settle_timeout
    )

    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(channel_identifier, B, A, b"").call()
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        ).call()


def test_channel_unlock(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    close_and_update_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """unlock() on pending transfers with unlockable and expired locks should
    split the locked amount accordingly, to both parties"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(deposit=20, transferred=5)
    values_B = ChannelValues(deposit=30, transferred=40)

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    values_B.locksroot = pending_transfers_tree.hash_of_packed_transfers
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settlement window must be over before settling the channel
    mine_blocks(web3, settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert info_B[ParticipantInfoIndex.LOCKSROOT] == values_B.locksroot
    assert info_B[ParticipantInfoIndex.LOCKED_AMOUNT] == values_B.locked_amounts.locked

    # Unlock the tokens
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        )
    )

    info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert info_B[ParticipantInfoIndex.LOCKSROOT] == NONEXISTENT_LOCKSROOT
    assert info_B[ParticipantInfoIndex.LOCKED_AMOUNT] == 0

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


@pytest.mark.slow
def test_channel_settle_and_unlock(
    web3: Web3,
    token_network: Contract,
    get_accounts: Callable,
    create_settled_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """Regular channel life-cycle: open -> settle -> unlock -> open -> settle -> unlock"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)

    # Settle the channel
    channel_identifier1 = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier1, B, A, pending_transfers_tree_1.packed_transfers
        ),
        {"from": A},
    )

    # Mock pending transfers data for a reopened channel
    pending_transfers_tree_2 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_2.unlockable)

    # Settle the channel again
    channel_identifier2 = create_settled_channel(
        A,
        pending_transfers_tree_2.locked_amount,
        pending_transfers_tree_2.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    # 2nd unlocks should go through
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier2, B, A, pending_transfers_tree_2.packed_transfers
        ),
        {"from": A},
    )

    # Edge channel life-cycle: open -> settle -> open -> settle ->  unlock1 -> unlock2

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)

    # Settle the channel
    channel_identifier3 = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    # Mock pending transfers data for a reopened channel
    pending_transfers_tree_2 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_2.unlockable)

    # Settle the channel again
    channel_identifier4 = create_settled_channel(
        A,
        pending_transfers_tree_2.locked_amount,
        pending_transfers_tree_2.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    # Both old and new unlocks should go through
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier4, B, A, pending_transfers_tree_2.packed_transfers
        ),
        {"from": A},
    )
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier3, B, A, pending_transfers_tree_1.packed_transfers
        ),
        {"from": A},
    )


def test_channel_unlock_registered_expired_lock_refunds(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    secret_registry_contract: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    close_and_update_channel: Callable,
) -> None:
    """unlock() should refund tokens locked with secrets revealed after the expiration"""
    (A, B) = get_accounts(2)
    max_lock_expiration = 3
    settle_timeout = 8

    values_A = ChannelValues(deposit=20, transferred=5)
    values_B = ChannelValues(deposit=30, transferred=40)

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(
        web3,
        [1, 3, 5],
        [2, 4],
        min_expiration_delta=max_lock_expiration - 2,
        max_expiration_delta=max_lock_expiration,
    )
    values_B.locksroot = pending_transfers_tree.hash_of_packed_transfers
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Locks expire
    mine_blocks(web3, max_lock_expiration)

    # Secrets are revealed before settlement window, but after expiration
    for (_, _, secrethash, secret) in pending_transfers_tree.unlockable:
        call_and_transact(secret_registry_contract.functions.registerSecret(secret), {"from": A})
        assert (
            secret_registry_contract.functions.getSecretRevealBlockHeight(secrethash).call()
            == web3.eth.block_number
        )

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)
    mine_blocks(web3, settle_timeout)

    # settle channel
    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock works after channel is settled
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        )
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # check that all tokens have been refunded, as locks have expired already
    assert balance_A == pre_balance_A
    assert balance_B == pre_balance_B + values_B.locked_amounts.locked
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


def test_channel_unlock_unregistered_locks(
    web3: Web3,
    token_network: Contract,
    get_accounts: Callable,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    close_and_update_channel: Callable,
    custom_token: Contract,
) -> None:
    """unlock() should refund tokens locked by secrets not registered before settlement"""
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN

    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    locked_A = pending_transfers_tree.locked_amount
    (vals_A, vals_B) = (
        ChannelValues(
            deposit=35,
            withdrawn=10,
            transferred=0,
            locked_amounts=LockedAmounts(claimable_locked=locked_A),
        ),
        ChannelValues(deposit=40, withdrawn=10, transferred=20),
    )

    vals_A.locksroot = pending_transfers_tree.hash_of_packed_transfers
    vals_B.locksroot = fake_bytes(32, "03")
    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)
    withdraw_channel(channel_identifier, A, vals_A.withdrawn, UINT256_MAX, B)
    withdraw_channel(channel_identifier, B, vals_B.withdrawn, UINT256_MAX, A)

    close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)

    # Secret hasn't been registered before settlement timeout
    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    # Someone unlocks A's pending transfers - all tokens should be refunded
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree.packed_transfers
        ),
        {"from": A},
    )

    # A gets back locked tokens
    assert (
        custom_token.functions.balanceOf(A).call()
        == vals_A.deposit - vals_A.transferred + vals_B.transferred
    )


def test_channel_unlock_before_settlement_fails(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    close_and_update_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """unlock() should not work before settlement"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(deposit=20, transferred=5)
    values_B = ChannelValues(deposit=30, transferred=40)

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    values_B.locksroot = pending_transfers_tree.hash_of_packed_transfers
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    # Unlock fails before channel is not settled
    with pytest.raises(TransactionFailed, match="TN/unlock: channel id still exists"):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Unlock fails before channel is not settled
    with pytest.raises(TransactionFailed, match="TN/unlock: channel id still exists"):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Unlock fails before settlement window is over and channel is not settled
    with pytest.raises(TransactionFailed, match="TN/unlock: channel id still exists"):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    # Settlement window must be over before settling the channel
    mine_blocks(web3, settle_timeout)

    # Unlock fails before settle is called
    with pytest.raises(TransactionFailed, match="TN/unlock: channel id still exists"):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    # settle channel
    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock works after channel is settled
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        )
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


def test_unlock_fails_with_partial_locks(
    web3: Web3,
    token_network: Contract,
    get_accounts: Callable,
    create_settled_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """unlock() should fail when one lock is missing"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree.locked_amount,
        pending_transfers_tree.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    # Unlock with one leave missing does not work
    types = ["uint256", "uint256", "bytes32"]
    for index in range(len(pending_transfers_tree.transfers)):
        pending_transfers = list(pending_transfers_tree.transfers)
        del pending_transfers[index]
        packed_transfers_tampered = get_packed_transfers(tuple(pending_transfers), types)
        with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
            token_network.functions.unlock(
                channel_identifier, B, A, packed_transfers_tampered
            ).call({"from": A})

    # Unlock with full pending locks does work
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree.packed_transfers
        ),
        {"from": A},
    )


def test_unlock_tampered_proof_fails(
    web3: Web3,
    token_network: Contract,
    get_accounts: Callable,
    create_settled_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """unlock() should fail when the submitted proofs are tampered"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree.locked_amount,
        pending_transfers_tree.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    # Unlock with tampered locks does not work
    types = ["uint256", "uint256", "bytes32"]
    for index in range(len(pending_transfers_tree.transfers)):
        pending_transfers = list(pending_transfers_tree.transfers)
        pending_transfers[index][2:] = random_secret()
        packed_transfers_tampered = get_packed_transfers(tuple(pending_transfers), types)
        with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
            token_network.functions.unlock(
                channel_identifier, B, A, packed_transfers_tampered
            ).call({"from": A})

    # Unlock with correct pending locks does work
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree.packed_transfers
        ),
        {"from": A},
    )


def test_channel_unlock_both_participants(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    secret_registry_contract: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    close_and_update_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """A scenario where both parties get some of the pending transfers"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(deposit=100, transferred=5)
    values_B = ChannelValues(deposit=100, transferred=40)

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data for A
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.hash_of_packed_transfers
    values_A.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree_A.transfers)
    )

    # Reveal A's secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    # Mock pending transfers data for B
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [2, 4, 6], [5, 10], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.hash_of_packed_transfers
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree_B.transfers)
    )

    # Reveal B's secrets before settlement window ends
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settle channel
    mine_blocks(web3, settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # A unlock's
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree_B.packed_transfers
        )
    )

    # B unlock's
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        )
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlocked pending transfers A -> B, that belong to B
    unlockable_A = get_unlocked_amount(
        secret_registry_contract, pending_transfers_tree_A.packed_transfers
    )

    # Expired pending transfers A -> B, that belong to A
    expired_A = get_locked_amount(pending_transfers_tree_A.expired)

    # Unlocked pending transfers B -> A, that belong to A
    unlockable_B = get_unlocked_amount(
        secret_registry_contract, pending_transfers_tree_B.packed_transfers
    )

    # Expired pending transfers B -> A, that belong to B
    expired_B = get_locked_amount(pending_transfers_tree_B.expired)

    # check that A and B both received the expected amounts
    assert balance_contract == (
        pre_balance_contract - values_B.locked_amounts.locked - values_A.locked_amounts.locked
    )
    assert balance_A == pre_balance_A + unlockable_B + expired_A
    assert balance_B == pre_balance_B + unlockable_A + expired_B


def test_unlock_twice_fails(
    web3: Web3,
    token_network: Contract,
    get_accounts: Callable,
    create_settled_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """The same unlock() call twice do not work"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_1.packed_transfers
        ),
        {"from": A},
    )

    # Calling unlock twice does not work
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_1.packed_transfers
        ).call({"from": A})


def test_unlock_no_locks(
    web3: Web3, token_network: Contract, get_accounts: Callable, create_settled_channel: Callable
) -> None:
    """unlock() should work on no pending locks"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(
        web3=web3,
        unlockable_amounts=[],
        expired_amounts=[2, 4],
        min_expiration_delta=settle_timeout,
    )

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree.locked_amount,
        pending_transfers_tree.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree.packed_transfers
        ),
        {"from": A},
    )

    # Calling unlock twice does not work
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree.packed_transfers
        ).call({"from": A})


def test_channel_unlock_with_a_large_expiration(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    close_and_update_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """unlock() should still work after a delayed settleChannel() call"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(deposit=20, transferred=5)
    values_B = ChannelValues(deposit=30, transferred=40)

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data with large expiration date
    pending_transfers_tree = get_pending_transfers_tree(
        web3, [1, 3, 5], [2, 4], settle_timeout + 100
    )
    values_B.locksroot = pending_transfers_tree.hash_of_packed_transfers
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settle channel after a "long" time
    mine_blocks(web3, settle_timeout + 50)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock the tokens must still work
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        )
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


def test_reverse_participants_unlock(
    web3: Web3,
    token_network: Contract,
    get_accounts: Callable,
    create_settled_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """unlock() with wrong argument orders"""
    (A, B, C) = get_accounts(3)
    settle_timeout = 12

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [3, 4, 6], [4], settle_timeout)
    assert (
        pending_transfers_tree_A.hash_of_packed_transfers
        != pending_transfers_tree_B.hash_of_packed_transfers
    )

    # Reveal secrets
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount,
        pending_transfers_tree_A.hash_of_packed_transfers,
        B,
        pending_transfers_tree_B.locked_amount,
        pending_transfers_tree_B.hash_of_packed_transfers,
        settle_timeout,
    )

    # A trying to unlock its own locksroot & locked amount MUST fail
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree_A.packed_transfers
        ).call({"from": A})

    # Delegate trying to unlock A's own locksroot & locked amount on behalf of A MUST fail
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree_A.packed_transfers
        ).call({"from": C})

    # B trying to unlock its own locksroot & locked amount MUST fail
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_B.packed_transfers
        ).call({"from": B})

    # Delegate trying to unlock B's own locksroot & locked amount on behalf of B MUST fail
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_B.packed_transfers
        ).call({"from": B})

    with pytest.raises(TransactionFailed, match="TN: identical addresses"):
        token_network.functions.unlock(
            channel_identifier, A, A, pending_transfers_tree_A.packed_transfers
        ).call({"from": A})

    with pytest.raises(TransactionFailed, match="TN: identical addresses"):
        token_network.functions.unlock(
            channel_identifier, B, B, pending_transfers_tree_B.packed_transfers
        ).call({"from": B})

    # Someone trying to unlock B's locksroot & locked amount on behalf of A MUST succeed
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree_B.packed_transfers
        ),
        {"from": C},
    )

    # Someone trying to unlock A's locksroot & locked amount on behalf of B MUST succeed
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        ),
        {"from": C},
    )


def test_unlock_different_channel_same_participants_fail(
    web3: Web3,
    token_network: Contract,
    get_accounts: Callable,
    create_settled_channel: Callable,
    reveal_secrets: Callable,
) -> None:
    """Try to confuse unlock() with two channels between the same participants"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    # The first channel is settled, so we create another one
    pending_transfers_tree_2 = get_pending_transfers_tree(web3, [3, 5], [2, 4, 3], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_2.unlockable)
    channel_identifier2 = create_settled_channel(
        A,
        pending_transfers_tree_2.locked_amount,
        pending_transfers_tree_2.hash_of_packed_transfers,
        B,
        0,
        LOCKSROOT_OF_NO_LOCKS,
        settle_timeout,
    )

    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_2.packed_transfers
        ).call({"from": A})
    with pytest.raises(TransactionFailed, match="TN/unlock: locksroot mismatch"):
        token_network.functions.unlock(
            channel_identifier2, B, A, pending_transfers_tree_1.packed_transfers
        ).call({"from": A})

    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_1.packed_transfers
        ),
        {"from": A},
    )
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier2, B, A, pending_transfers_tree_2.packed_transfers
        ),
        {"from": A},
    )


def test_unlock_channel_event(
    web3: Web3,
    token_network: Contract,
    secret_registry_contract: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    close_and_update_channel: Callable,
    reveal_secrets: Callable,
    event_handler: Callable,
) -> None:
    """Successful unlock() should cause an UNLOCKED event"""
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(deposit=20, transferred=5)
    values_B = ChannelValues(deposit=30, transferred=40)

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(
        web3, [1, 3, 5], [2, 4], settle_timeout + 100
    )
    values_B.locksroot = pending_transfers_tree.hash_of_packed_transfers
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settlement window must be over before settling the channel
    mine_blocks(web3, settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    ev_handler = event_handler(token_network)

    # Unlock the tokens
    txn_hash = call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        )
    )

    unlocked_amount = get_unlocked_amount(
        secret_registry_contract, pending_transfers_tree.packed_transfers
    )

    # Add event
    ev_handler.add(
        txn_hash,
        ChannelEvent.UNLOCKED,
        check_channel_unlocked(
            channel_identifier,
            A,
            B,
            values_B.locksroot,
            unlocked_amount,
            values_B.locked_amounts.locked - unlocked_amount,
        ),
    )

    # Check that event was properly emitted
    ev_handler.check()
