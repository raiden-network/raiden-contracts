import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ChannelEvent, ParticipantInfoIndex
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.utils import (
    EMPTY_LOCKSROOT,
    ChannelValues,
    LockedAmounts,
    TestLockIndex,
    fake_bytes,
    get_unlocked_amount,
)
from raiden_contracts.utils import (
    get_locked_amount,
    get_packed_transfers,
    get_pending_transfers_tree,
    random_secret,
)
from raiden_contracts.utils.events import check_channel_unlocked
from raiden_contracts.utils.merkle import get_merkle_root

# Account names like 'A', 'B', 'C' are intuitive here.
# pytest: disable=C0103


def test_merkle_root_0_items(token_network_test_utils):
    """ getMerkleRootAndUnlockedAmount() returns a reasonable return value for no items """
    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getMerkleRootAndUnlockedAmountPublic(b"").call()
    assert locksroot == EMPTY_LOCKSROOT
    assert unlocked_amount == 0


def test_merkle_root_1_item_unlockable(
    web3, get_accounts, token_network_test_utils, secret_registry_contract
):
    """ Test getMerkleRootAndUnlockedAmount() on a single item whose secret has been registered """
    A = get_accounts(1)[0]
    pending_transfers_tree = get_pending_transfers_tree(web3, [6])

    secret_registry_contract.functions.registerSecret(
        pending_transfers_tree.unlockable[0][TestLockIndex.SECRET]
    ).call_and_transact({"from": A})
    assert (
        secret_registry_contract.functions.getSecretRevealBlockHeight(
            pending_transfers_tree.unlockable[0][TestLockIndex.SECRETHASH]
        ).call()
        == web3.eth.blockNumber
    )

    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getMerkleRootAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()

    merkle_root = pending_transfers_tree.merkle_root
    assert locksroot == merkle_root
    assert unlocked_amount == 6


def test_merkle_tree_length_fail(
    web3, get_accounts, token_network_test_utils, secret_registry_contract
):
    """ Test getMerkleRootAndUnlockedAmount() on inputs of irregular lengths """
    network_utils = token_network_test_utils
    A = get_accounts(1)[0]
    pending_transfers_tree = get_pending_transfers_tree(web3, [2, 3, 6], [5])

    secret_registry_contract.functions.registerSecret(
        pending_transfers_tree.unlockable[0][TestLockIndex.SECRET]
    ).call_and_transact({"from": A})
    assert (
        secret_registry_contract.functions.getSecretRevealBlockHeight(
            pending_transfers_tree.unlockable[0][TestLockIndex.SECRETHASH]
        ).call()
        == web3.eth.blockNumber
    )

    packed = pending_transfers_tree.packed_transfers

    # packed length must be a multiple of 96
    with pytest.raises(TransactionFailed):
        network_utils.functions.getMerkleRootAndUnlockedAmountPublic(packed[0:-1]).call()
    # last merkle tree component only contains expiration + locked_amount
    with pytest.raises(TransactionFailed):
        network_utils.functions.getMerkleRootAndUnlockedAmountPublic(packed[0:-32]).call()
    # last merkle tree component only contains expiration
    with pytest.raises(TransactionFailed):
        network_utils.functions.getMerkleRootAndUnlockedAmountPublic(packed[0:-64]).call()

    assert len(packed) % 96 == 0
    network_utils.functions.getMerkleRootAndUnlockedAmountPublic(packed).call()
    network_utils.functions.getMerkleRootAndUnlockedAmountPublic(packed[0:-96]).call()


def test_merkle_root_odd_even_components(
    web3, get_accounts, token_network_test_utils, reveal_secrets
):
    """ Test getMerkleRootAndUnlockedAmount() on an odd/even number of locks """
    A = get_accounts(1)[0]

    # Even number of merkle tree components
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8, 3])
    reveal_secrets(A, pending_transfers_tree.unlockable)

    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getMerkleRootAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()
    merkle_root = pending_transfers_tree.merkle_root

    assert locksroot == merkle_root
    assert unlocked_amount == 9

    # Odd number of merkle tree components
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8])
    reveal_secrets(A, pending_transfers_tree.unlockable)

    (
        locksroot,
        unlocked_amount,
    ) = token_network_test_utils.functions.getMerkleRootAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()
    merkle_root = pending_transfers_tree.merkle_root

    assert locksroot == merkle_root
    assert unlocked_amount == 9


def test_merkle_tree_components_order(
    web3,
    get_accounts,
    token_network_test_utils,
    reveal_secrets,
    token_network,
    create_settled_channel,
):
    """ Shuffling the leaves usually changes the root, but sometimes not """
    network_utils = token_network_test_utils
    (A, B) = get_accounts(2)
    types = ["uint256", "uint256", "bytes32"]

    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8, 3])
    reveal_secrets(A, pending_transfers_tree.unlockable)

    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree.locked_amount,
        pending_transfers_tree.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
    )

    # Merkle tree lockhashes are ordered lexicographicaly.
    # If we change the order, we change the computed merkle root.
    # However, the getMerkleRootAndUnlockedAmount orders neighbouring lockhashes
    # lexicographicaly, so simple item[i], item[i + 1] swap
    # will still result in the same merkle root.
    wrong_order = pending_transfers_tree.transfers
    wrong_order[1], wrong_order[0] = wrong_order[0], wrong_order[1]
    wrong_order_packed = get_packed_transfers(wrong_order, types)
    (locksroot, unlocked_amount) = network_utils.functions.getMerkleRootAndUnlockedAmountPublic(
        wrong_order_packed
    ).call()
    # Same merkle root this time
    assert locksroot == pending_transfers_tree.merkle_root
    assert unlocked_amount == 9
    token_network.functions.unlock(channel_identifier, B, A, wrong_order_packed).call()

    wrong_order = pending_transfers_tree.transfers
    wrong_order[2], wrong_order[0] = wrong_order[0], wrong_order[2]
    wrong_order_packed = get_packed_transfers(wrong_order, types)
    (locksroot, unlocked_amount) = network_utils.functions.getMerkleRootAndUnlockedAmountPublic(
        wrong_order_packed
    ).call()
    assert locksroot != pending_transfers_tree.merkle_root
    assert unlocked_amount == 9
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(channel_identifier, B, A, wrong_order_packed).call()

    wrong_order = pending_transfers_tree.transfers
    wrong_order[0], wrong_order[-1] = wrong_order[-1], wrong_order[0]
    wrong_order_packed = get_packed_transfers(wrong_order, types)
    (locksroot, unlocked_amount) = network_utils.functions.getMerkleRootAndUnlockedAmountPublic(
        wrong_order_packed
    ).call()
    assert locksroot != pending_transfers_tree.merkle_root
    assert unlocked_amount == 9
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(channel_identifier, B, A, wrong_order_packed).call()

    (locksroot, unlocked_amount) = network_utils.functions.getMerkleRootAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    ).call()
    assert locksroot == pending_transfers_tree.merkle_root
    assert unlocked_amount == 9
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree.packed_transfers
    ).call_and_transact()


def test_lock_data_from_merkle_tree(
    web3, get_accounts, token_network_test_utils, secret_registry_contract, reveal_secrets
):
    """ Test getLockDataFromMerkleTreePublic() on various offsets """
    network_utils = token_network_test_utils
    A = get_accounts(1)[0]

    unlockable_amounts = [3, 5]
    expired_amounts = [2, 8, 7]
    pending_transfers_tree = get_pending_transfers_tree(
        web3, unlockable_amounts, expired_amounts, max_expiration_delta=5
    )
    reveal_secrets(A, pending_transfers_tree.unlockable)

    def claimable(index):
        amount = pending_transfers_tree.transfers[index][1]
        return amount if amount in unlockable_amounts else 0

    def get_lockhash(index):
        return pending_transfers_tree.merkle_tree.layers[0][index]

    # Lock data is ordered lexicographically, regardless of expiration status
    (lockhash, claimable_amount) = network_utils.functions.getLockDataFromMerkleTreePublic(
        pending_transfers_tree.packed_transfers, 32
    ).call()
    assert lockhash == get_lockhash(0)
    assert claimable_amount == claimable(0)

    (lockhash, claimable_amount) = network_utils.functions.getLockDataFromMerkleTreePublic(
        pending_transfers_tree.packed_transfers, 32 + 96
    ).call()
    assert lockhash == get_lockhash(1)
    assert claimable_amount == claimable(1)

    (lockhash, claimable_amount) = network_utils.functions.getLockDataFromMerkleTreePublic(
        pending_transfers_tree.packed_transfers, 32 + 2 * 96
    ).call()
    assert lockhash == get_lockhash(2)
    assert claimable_amount == claimable(2)

    (lockhash, claimable_amount) = network_utils.functions.getLockDataFromMerkleTreePublic(
        pending_transfers_tree.packed_transfers, 32 + 3 * 96
    ).call()
    assert lockhash == get_lockhash(3)
    assert claimable_amount == claimable(3)

    (lockhash, claimable_amount) = network_utils.functions.getLockDataFromMerkleTreePublic(
        pending_transfers_tree.packed_transfers, 32 + 4 * 96
    ).call()
    assert lockhash == get_lockhash(4)
    assert claimable_amount == claimable(4)

    # Register last secret after expiration
    web3.testing.mine(5)
    last_lock = pending_transfers_tree.expired[-1]
    # expiration
    assert web3.eth.blockNumber > last_lock[0]
    # register secret
    secret_registry_contract.functions.registerSecret(last_lock[3]).call_and_transact()
    # ensure registration was done
    assert (
        secret_registry_contract.functions.getSecretRevealBlockHeight(last_lock[2]).call()
        == web3.eth.blockNumber
    )

    # Check that last secret is still regarded as expired
    (lockhash, claimable_amount) = network_utils.functions.getLockDataFromMerkleTreePublic(
        pending_transfers_tree.packed_transfers, 32 + 4 * 96
    ).call()
    assert lockhash == get_lockhash(4)
    assert claimable_amount == claimable(4)

    # If the offset is bigger than the length of the merkle tree, return (0, 0)
    (lockhash, claimable_amount) = network_utils.functions.getLockDataFromMerkleTreePublic(
        pending_transfers_tree.packed_transfers, 32 + 5 * 96
    ).call()
    assert lockhash == b"\x00" * 32
    assert claimable_amount == 0


def test_unlock_wrong_locksroot(web3, token_network, create_settled_channel, get_accounts):
    """ Test unlocking with wrong Merkle tree entries """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [], settle_timeout)
    pending_transfers_tree_A_fake = get_pending_transfers_tree(web3, [1, 3, 6], [], settle_timeout)

    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount,
        pending_transfers_tree_A.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A_fake.packed_transfers
        ).call()

    # Fails for an empty merkle tree
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(channel_identifier, B, A, b"").call()

    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
    ).call_and_transact()


def test_channel_unlock_bigger_locked_amount(
    web3,
    token_network,
    custom_token,
    secret_registry_contract,
    create_settled_channel,
    get_accounts,
    reveal_secrets,
):
    """ Test an unlock() call that claims too little tokens"

    When an unlock() call does not contain enough Merkle tree leaves to claim
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
    # actual merkle tree of pending transfers
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount + 1,
        pending_transfers_tree_A.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == pending_transfers_tree_A.locked_amount + 1

    # This should pass, even though the locked amount in storage is bigger. The rest of the
    # tokens is sent to A, as tokens corresponding to the locks that could not be unlocked.
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
    ).call_and_transact()
    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == (
        pre_balance_A + pending_transfers_tree_A.locked_amount - unlocked_amount + 1
    )
    assert balance_B == pre_balance_B + unlocked_amount
    assert balance_contract == 0


def test_channel_unlock_smaller_locked_amount(
    web3,
    token_network,
    custom_token,
    secret_registry_contract,
    create_settled_channel,
    get_accounts,
    reveal_secrets,
):
    """ Test an unlock() call that claims too many tokens

    When settleChannel() call computes a smaller amount of locked tokens than
    the following unlock() call, the settleChannel() computation is stronger and
    the participant receives less tokens. Stealing tokens from other channels
    is then prevented. """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    unlocked_amount = get_unlocked_amount(
        secret_registry_contract, pending_transfers_tree_A.packed_transfers
    )

    # We settle the channel with a smaller locked amount than we will need for the
    # actual merkle tree of pending transfers
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount - 1,
        pending_transfers_tree_A.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == pending_transfers_tree_A.locked_amount - 1

    # This should pass, even though the locked amount in storage is smaller.
    # B will receive less tokens.
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
    ).call_and_transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == (
        pre_balance_A + pending_transfers_tree_A.locked_amount - unlocked_amount - 1
    )
    assert balance_B == pre_balance_B + unlocked_amount
    assert balance_contract == 0


def test_channel_unlock_bigger_unlocked_amount(
    web3,
    token_network,
    custom_token,
    secret_registry_contract,
    create_settled_channel,
    get_accounts,
    reveal_secrets,
):
    """ unlock() transfers not more than the locked amount for more expensive unlock() demands """
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
        pending_transfers_tree_A.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == unlocked_amount - 1

    # This should pass, even though the locked amount in storage is smaller.
    # B will receive the entire locked amount, corresponding to the locks that have been unlocked
    # and A will receive nothing.
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
    ).call_and_transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A
    assert balance_B == pre_balance_B + unlocked_amount - 1
    assert balance_contract == 0


def test_channel_unlock_no_locked_amount_fail(
    web3, token_network, create_settled_channel, get_accounts, reveal_secrets
):
    """ After settleChannel() is called with zero locked amount, unlock() calls fail """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [2, 5], [4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    channel_identifier = create_settled_channel(
        A, 0, EMPTY_LOCKSROOT, B, 0, EMPTY_LOCKSROOT, settle_timeout
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(channel_identifier, B, A, b"").call()
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        ).call()


def test_channel_unlock(
    web3,
    custom_token,
    token_network,
    create_channel,
    channel_deposit,
    get_accounts,
    close_and_update_channel,
    reveal_secrets,
):
    """ unlock() on pending transfers with unlockable and expired locks should
    split the locked amount accordingly, to both parties """
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
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert info_B[ParticipantInfoIndex.LOCKSROOT] == values_B.locksroot
    assert info_B[ParticipantInfoIndex.LOCKED_AMOUNT] == values_B.locked_amounts.locked

    # Unlock the tokens
    token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree.packed_transfers
    ).call_and_transact()

    info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert info_B[ParticipantInfoIndex.LOCKSROOT] == EMPTY_LOCKSROOT
    assert info_B[ParticipantInfoIndex.LOCKED_AMOUNT] == 0

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


@pytest.mark.slow
def test_channel_settle_and_unlock(
    web3, token_network, get_accounts, create_settled_channel, reveal_secrets
):
    """ Regular channel life-cycle: open -> settle -> unlock -> open -> settle -> unlock """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)

    # Settle the channel
    channel_identifier1 = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )
    token_network.functions.unlock(
        channel_identifier1, B, A, pending_transfers_tree_1.packed_transfers
    ).call_and_transact({"from": A})

    # Mock pending transfers data for a reopened channel
    pending_transfers_tree_2 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_2.unlockable)

    # Settle the channel again
    channel_identifier2 = create_settled_channel(
        A,
        pending_transfers_tree_2.locked_amount,
        pending_transfers_tree_2.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    # 2nd unlocks should go through
    token_network.functions.unlock(
        channel_identifier2, B, A, pending_transfers_tree_2.packed_transfers
    ).call_and_transact({"from": A})

    # Edge channel life-cycle: open -> settle -> open -> settle ->  unlock1 -> unlock2

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)

    # Settle the channel
    channel_identifier3 = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    # Mock pending transfers data for a reopened channel
    pending_transfers_tree_2 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_2.unlockable)

    # Settle the channel again
    channel_identifier4 = create_settled_channel(
        A,
        pending_transfers_tree_2.locked_amount,
        pending_transfers_tree_2.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    # Both old and new unlocks should go through
    token_network.functions.unlock(
        channel_identifier4, B, A, pending_transfers_tree_2.packed_transfers
    ).call_and_transact({"from": A})
    token_network.functions.unlock(
        channel_identifier3, B, A, pending_transfers_tree_1.packed_transfers
    ).call_and_transact({"from": A})


def test_channel_unlock_registered_expired_lock_refunds(
    web3,
    custom_token,
    token_network,
    secret_registry_contract,
    create_channel,
    channel_deposit,
    get_accounts,
    close_and_update_channel,
):
    """ unlock() should refund tokens locked with secrets revealed after the expiration """
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
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Locks expire
    web3.testing.mine(max_lock_expiration)

    # Secrets are revealed before settlement window, but after expiration
    for (_, _, secrethash, secret) in pending_transfers_tree.unlockable:
        secret_registry_contract.functions.registerSecret(secret).call_and_transact({"from": A})
        assert (
            secret_registry_contract.functions.getSecretRevealBlockHeight(secrethash).call()
            == web3.eth.blockNumber
        )

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)
    web3.testing.mine(settle_timeout)

    # settle channel
    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock works after channel is settled
    token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree.packed_transfers
    ).call_and_transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # check that all tokens have been refunded, as locks have expired already
    assert balance_A == pre_balance_A
    assert balance_B == pre_balance_B + values_B.locked_amounts.locked
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


def test_channel_unlock_unregistered_locks(
    web3,
    token_network,
    get_accounts,
    create_channel_and_deposit,
    withdraw_channel,
    close_and_update_channel,
    custom_token,
):
    """ unlock() should refund tokens locked by secrets not registered before settlement """
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

    vals_A.locksroot = "0x" + get_merkle_root(pending_transfers_tree.merkle_tree).hex()
    vals_B.locksroot = fake_bytes(32, "03")
    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)
    withdraw_channel(channel_identifier, A, vals_A.withdrawn, B)
    withdraw_channel(channel_identifier, B, vals_B.withdrawn, A)

    close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)

    # Secret hasn't been registered before settlement timeout
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN + 1)
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    # Someone unlocks A's pending transfers - all tokens should be refunded
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree.packed_transfers
    ).call_and_transact({"from": A})

    # A gets back locked tokens
    assert (
        custom_token.functions.balanceOf(A).call()
        == vals_A.deposit - vals_A.transferred + vals_B.transferred
    )


def test_channel_unlock_before_settlement_fails(
    web3,
    custom_token,
    token_network,
    create_channel,
    channel_deposit,
    get_accounts,
    close_and_update_channel,
    reveal_secrets,
):
    """ unlock() should not work before settlement """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(deposit=20, transferred=5)
    values_B = ChannelValues(deposit=30, transferred=40)

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    # Unlock fails before channel is not settled
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Unlock fails before channel is not settled
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Unlock fails before settlement window is over and channel is not settled
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    # Unlock fails before settle is called
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree.packed_transfers
        ).call()

    # settle channel
    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock works after channel is settled
    token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree.packed_transfers
    ).call_and_transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


def test_unlock_fails_with_partial_merkle_proof(
    web3, token_network, get_accounts, create_settled_channel, reveal_secrets
):
    """ unlock() should fail when one Merkle leaf is missing """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree.locked_amount,
        pending_transfers_tree.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    # Unlock with one leave missing does not work
    types = ["uint256", "uint256", "bytes32"]
    for index in range(len(pending_transfers_tree.transfers)):
        pending_transfers = list(pending_transfers_tree.transfers)
        del pending_transfers[index]
        packed_transfers_tampered = get_packed_transfers(tuple(pending_transfers), types)
        with pytest.raises(TransactionFailed):
            token_network.functions.unlock(
                channel_identifier, B, A, packed_transfers_tampered
            ).call({"from": A})

    # Unlock with full merkle tree does work
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree.packed_transfers
    ).call_and_transact({"from": A})


def test_unlock_tampered_merkle_proof_fails(
    web3, token_network, get_accounts, create_settled_channel, reveal_secrets
):
    """ unlock() should fail when the submitted proofs are tampered """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree.locked_amount,
        pending_transfers_tree.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    # Unlock with tampered locks does not work
    types = ["uint256", "uint256", "bytes32"]
    for index in range(len(pending_transfers_tree.transfers)):
        pending_transfers = list(pending_transfers_tree.transfers)
        pending_transfers[index][2:] = random_secret()
        packed_transfers_tampered = get_packed_transfers(tuple(pending_transfers), types)
        with pytest.raises(TransactionFailed):
            token_network.functions.unlock(
                channel_identifier, B, A, packed_transfers_tampered
            ).call({"from": A})

    # Unlock with correct merkle tree does work
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree.packed_transfers
    ).call_and_transact({"from": A})


def test_channel_unlock_both_participants(
    web3,
    custom_token,
    token_network,
    secret_registry_contract,
    create_channel,
    channel_deposit,
    get_accounts,
    close_and_update_channel,
    reveal_secrets,
):
    """ A scenario where both parties get some of the pending transfers """
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
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    values_A.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree_A.transfers)
    )

    # Reveal A's secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    # Mock pending transfers data for B
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [2, 4, 6], [5, 10], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree_B.transfers)
    )

    # Reveal B's secrets before settlement window ends
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settle channel
    web3.testing.mine(settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # A unlock's
    token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree_B.packed_transfers
    ).call_and_transact()

    # B unlock's
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
    ).call_and_transact()

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
    web3, token_network, get_accounts, create_settled_channel, reveal_secrets
):
    """ The same unlock() call twice do not work """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_1.packed_transfers
    ).call_and_transact({"from": A})

    # Calling unlock twice does not work
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_1.packed_transfers
        ).call({"from": A})


def test_channel_unlock_with_a_large_expiration(
    web3,
    custom_token,
    token_network,
    create_channel,
    channel_deposit,
    get_accounts,
    close_and_update_channel,
    reveal_secrets,
):
    """ unlock() should still work after a delayed settleChannel() call """
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
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settle channel after a "long" time
    web3.testing.mine(settle_timeout + 50)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock the tokens must still work
    token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree.packed_transfers
    ).call_and_transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked_amounts.locked


def test_reverse_participants_unlock(
    web3, token_network, get_accounts, create_settled_channel, reveal_secrets
):
    """ unlock() with wrong argument orders """
    (A, B, C) = get_accounts(3)
    settle_timeout = 12

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [3, 4, 6], [4], settle_timeout)
    assert pending_transfers_tree_A.merkle_root != pending_transfers_tree_B.merkle_root

    # Reveal secrets
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Settle the channel
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount,
        pending_transfers_tree_A.merkle_root,
        B,
        pending_transfers_tree_B.locked_amount,
        pending_transfers_tree_B.merkle_root,
        settle_timeout,
    )

    # A trying to unlock its own locksroot & locked amount MUST fail
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree_A.packed_transfers
        ).call({"from": A})

    # Delegate trying to unlock A's own locksroot & locked amount on behalf of A MUST fail
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree_A.packed_transfers
        ).call({"from": C})

    # B trying to unlock its own locksroot & locked amount MUST fail
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_B.packed_transfers
        ).call({"from": B})

    # Delegate trying to unlock B's own locksroot & locked amount on behalf of B MUST fail
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_B.packed_transfers
        ).call({"from": B})

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, A, A, pending_transfers_tree_A.packed_transfers
        ).call({"from": A})

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, B, B, pending_transfers_tree_B.packed_transfers
        ).call({"from": B})

    # Someone trying to unlock B's locksroot & locked amount on behalf of A MUST succeed
    token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree_B.packed_transfers
    ).call_and_transact({"from": C})

    # Someone trying to unlock A's locksroot & locked amount on behalf of B MUST succeed
    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
    ).call_and_transact({"from": C})


def test_unlock_different_channel_same_participants_fail(
    web3, token_network, get_accounts, create_settled_channel, reveal_secrets
):
    """ Try to confuse unlock() with two channels between the same participants """
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_1 = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_1.unlockable)
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_1.locked_amount,
        pending_transfers_tree_1.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    # The first channel is settled, so we create another one
    pending_transfers_tree_2 = get_pending_transfers_tree(web3, [3, 5], [2, 4, 3], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_2.unlockable)
    channel_identifier2 = create_settled_channel(
        A,
        pending_transfers_tree_2.locked_amount,
        pending_transfers_tree_2.merkle_root,
        B,
        0,
        EMPTY_LOCKSROOT,
        settle_timeout,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_2.packed_transfers
        ).call({"from": A})
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier2, B, A, pending_transfers_tree_1.packed_transfers
        ).call({"from": A})

    token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree_1.packed_transfers
    ).call_and_transact({"from": A})
    token_network.functions.unlock(
        channel_identifier2, B, A, pending_transfers_tree_2.packed_transfers
    ).call_and_transact({"from": A})


def test_unlock_channel_event(
    web3,
    token_network,
    secret_registry_contract,
    create_channel,
    channel_deposit,
    get_accounts,
    close_and_update_channel,
    reveal_secrets,
    event_handler,
):
    """ Successful unlock() should cause an UNLOCKED event """
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
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked_amounts = LockedAmounts(
        claimable_locked=get_locked_amount(pending_transfers_tree.transfers)
    )

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(channel_identifier, A, values_A, B, values_B)

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    ev_handler = event_handler(token_network)

    # Unlock the tokens
    txn_hash = token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree.packed_transfers
    ).call_and_transact()

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
