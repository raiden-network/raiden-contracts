import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.constants import ChannelEvent
from raiden_contracts.utils.events import check_channel_unlocked
from .utils import (
    get_pending_transfers_tree,
    get_unlocked_amount,
    get_locked_amount,
    get_packed_transfers,
    random_secret,
)
from raiden_contracts.utils.merkle import EMPTY_MERKLE_ROOT
from raiden_contracts.tests.utils import ChannelValues
from raiden_contracts.tests.fixtures.channel import call_settle


def test_merkle_root_0_items(token_network_test):
    (
        locksroot,
        unlocked_amount,
    ) = token_network_test.functions.getMerkleRootAndUnlockedAmountPublic(b'').call()
    assert locksroot == EMPTY_MERKLE_ROOT
    assert unlocked_amount == 0


def test_merkle_root_1_item_unlockable(
        web3,
        get_accounts,
        token_network_test,
        secret_registry_contract,
):
    A = get_accounts(1)[0]
    pending_transfers_tree = get_pending_transfers_tree(web3, [6])

    secret_registry_contract.functions.registerSecret(
        pending_transfers_tree.unlockable[0][3],
    ).transact({'from': A})
    assert secret_registry_contract.functions.getSecretRevealBlockHeight(
        pending_transfers_tree.unlockable[0][2],
    ).call() == web3.eth.blockNumber

    (locksroot, unlocked_amount) = token_network_test.functions.getMerkleRootAndUnlockedAmountPublic(  # noqa
        pending_transfers_tree.packed_transfers,
    ).call()

    merkle_root = pending_transfers_tree.merkle_root
    assert locksroot == merkle_root
    assert unlocked_amount == 6


def test_merkle_root(
        web3,
        get_accounts,
        token_network_test,
        secret_registry_contract,
        reveal_secrets,
):
    (A, B) = get_accounts(2)
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8, 3])

    reveal_secrets(A, pending_transfers_tree.unlockable)

    (locksroot, unlocked_amount) = token_network_test.functions.getMerkleRootAndUnlockedAmountPublic(  # noqa
        pending_transfers_tree.packed_transfers,
    ).call()
    merkle_root = pending_transfers_tree.merkle_root

    assert locksroot == merkle_root
    assert unlocked_amount == 9


def test_unlock_wrong_locksroot(
        web3,
        token_network,
        create_settled_channel,
        get_accounts,
):
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
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            B,
            A,
            pending_transfers_tree_A_fake.packed_transfers,
        ).call()

    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).call()


def test_channel_unlock_bigger_locked_amount(
        web3,
        token_network,
        custom_token,
        secret_registry_contract,
        create_settled_channel,
        get_accounts,
        reveal_secrets,
):
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    unlocked_amount = get_unlocked_amount(
        secret_registry_contract,
        pending_transfers_tree_A.packed_transfers,
    )

    # We settle the channel with a bigger locked amount than we will need for the
    # actual merkle tree of pending transfers
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount + 1,
        pending_transfers_tree_A.merkle_root,
        B,
        0,
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == pending_transfers_tree_A.locked_amount + 1

    # This should pass, even though the locked amount in storage is bigger. The rest of the
    # tokens is sent to A, as tokens corresponding to the locks that could not be unlocked.
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()
    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == (
        pre_balance_A +
        pending_transfers_tree_A.locked_amount -
        unlocked_amount + 1
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
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    unlocked_amount = get_unlocked_amount(
        secret_registry_contract,
        pending_transfers_tree_A.packed_transfers,
    )

    # We settle the channel with a smaller locked amount than we will need for the
    # actual merkle tree of pending transfers
    channel_identifier = create_settled_channel(
        A,
        pending_transfers_tree_A.locked_amount - 1,
        pending_transfers_tree_A.merkle_root,
        B,
        0,
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == pending_transfers_tree_A.locked_amount - 1

    # This should pass, even though the locked amount in storage is smaller.
    # B will receive less tokens.
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == (
        pre_balance_A +
        pending_transfers_tree_A.locked_amount -
        unlocked_amount - 1
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
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Mock pending transfers data
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    unlocked_amount = get_unlocked_amount(
        secret_registry_contract,
        pending_transfers_tree_A.packed_transfers,
    )
    assert unlocked_amount < pending_transfers_tree_A.locked_amount

    # We settle the channel with a smaller locked amount than the amount that can be unlocked
    channel_identifier = create_settled_channel(
        A,
        unlocked_amount - 1,
        pending_transfers_tree_A.merkle_root,
        B,
        0,
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_contract == unlocked_amount - 1

    # This should pass, even though the locked amount in storage is smaller.
    # A will receive the entire locked amount, corresponding to the locks that have been unlocked
    # and B will receive nothing.
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A
    assert balance_B == pre_balance_B + unlocked_amount - 1
    assert balance_contract == 0


def test_channel_unlock(
        web3,
        custom_token,
        token_network,
        secret_registry_contract,
        create_channel,
        channel_deposit,
        get_accounts,
        close_and_update_channel,
        reveal_secrets,
        event_handler,
):
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(
        deposit=20,
        transferred=5,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    values_B = ChannelValues(
        deposit=30,
        transferred=40,
    )

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked = get_locked_amount(pending_transfers_tree.transfers)

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(
        channel_identifier,
        A,
        values_A,
        B,
        values_B,
    )

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock the tokens
    token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree.packed_transfers,
    ).transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked


def test_channel_settle_and_unlock(
        web3,
        token_network,
        get_accounts,
        create_settled_channel,
        reveal_secrets,
):
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Regular channel life-cycle: open -> settle -> unlock -> open -> settle -> unlock

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
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )
    token_network.functions.unlock(
        channel_identifier1,
        B,
        A,
        pending_transfers_tree_1.packed_transfers,
    ).transact({'from': A})

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
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    # 2nd unlocks should go through
    token_network.functions.unlock(
        channel_identifier2,
        B,
        A,
        pending_transfers_tree_2.packed_transfers,
    ).transact({'from': A})

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
        EMPTY_MERKLE_ROOT,
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
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    # Both old and new unlocks should go through
    token_network.functions.unlock(
        channel_identifier4,
        B,
        A,
        pending_transfers_tree_2.packed_transfers,
    ).transact({'from': A})
    token_network.functions.unlock(
        channel_identifier3,
        B,
        A,
        pending_transfers_tree_1.packed_transfers,
    ).transact({'from': A})


def test_channel_unlock_expired_lock_refunds(
        web3,
        custom_token,
        token_network,
        secret_registry_contract,
        create_channel,
        channel_deposit,
        get_accounts,
        reveal_secrets,
        close_and_update_channel,
):
    (A, B) = get_accounts(2)
    max_lock_expiration = 3
    settle_timeout = 8

    values_A = ChannelValues(
        deposit=20,
        transferred=5,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    values_B = ChannelValues(
        deposit=30,
        transferred=40,
    )

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
    values_B.locked = get_locked_amount(pending_transfers_tree.transfers)

    # Locks expire
    web3.testing.mine(max_lock_expiration)

    # Secrets are revealed before settlement window, but after expiration
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(
        channel_identifier,
        A,
        values_A,
        B,
        values_B,
    )
    web3.testing.mine(settle_timeout)

    # settle channel
    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock works after channel is settled
    token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree.packed_transfers,
    ).transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # check that all tokens have been refunded, as locks have expired already
    assert balance_A == pre_balance_A
    assert balance_B == pre_balance_B + values_B.locked
    assert balance_contract == pre_balance_contract - values_B.locked


def test_channel_unlock_before_settlement_fails(
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
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(
        deposit=20,
        transferred=5,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    values_B = ChannelValues(
        deposit=30,
        transferred=40,
    )

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked = get_locked_amount(pending_transfers_tree.transfers)

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(
        channel_identifier,
        A,
        values_A,
        B,
        values_B,
    )

    # Unlock fails before settlement window is over and channel is not settled
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            A,
            B,
            pending_transfers_tree.packed_transfers,
        ).transact()

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)
    # Unlock fails before settle is called
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            A,
            B,
            pending_transfers_tree.packed_transfers,
        ).transact()

    # settle channel
    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock works after channel is settled
    token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree.packed_transfers,
    ).transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked


def test_unlock_fails_with_partial_merkle_proof(
        web3,
        token_network,
        get_accounts,
        create_settled_channel,
        reveal_secrets,
):
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
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    # Unlock with one leave missing does not work
    types = ['uint256', 'uint256', 'bytes32']
    for index in range(len(pending_transfers_tree.transfers)):
        pending_transfers = list(pending_transfers_tree.transfers)
        del pending_transfers[index]
        packed_transfers_tampered = get_packed_transfers(tuple(pending_transfers), types)
        with pytest.raises(TransactionFailed):
            token_network.functions.unlock(
                channel_identifier,
                B,
                A,
                packed_transfers_tampered,
            ).transact({'from': A})

    # Unlock with full merkle tree does work
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree.packed_transfers,
    ).transact({'from': A})


def test_unlock_tampered_merkle_proof_fails(
        web3,
        token_network,
        get_accounts,
        create_settled_channel,
        reveal_secrets,
):
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Regular channel life-cycle: open -> settle -> unlock -> open -> settle -> unlock

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
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )

    # Unlock with tampered locks does not work
    types = ['uint256', 'uint256', 'bytes32']
    for index in range(len(pending_transfers_tree.transfers)):
        pending_transfers = list(pending_transfers_tree.transfers)
        pending_transfers[index][2:] = random_secret()
        packed_transfers_tampered = get_packed_transfers(tuple(pending_transfers), types)
        with pytest.raises(TransactionFailed):
            token_network.functions.unlock(
                channel_identifier,
                B,
                A,
                packed_transfers_tampered,
            ).transact({'from': A})

    # Unlock with correct merkle tree does work
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree.packed_transfers,
    ).transact({'from': A})


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
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(
        deposit=100,
        transferred=5,
    )
    values_B = ChannelValues(
        deposit=100,
        transferred=40,
    )

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data for A
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    values_A.locked = get_locked_amount(pending_transfers_tree_A.transfers)

    # Reveal A's secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    # Mock pending transfers data for B
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [2, 4, 6], [5, 10], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    values_B.locked = get_locked_amount(pending_transfers_tree_B.transfers)

    # Reveal B's secrets before settlement window ends
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    close_and_update_channel(
        channel_identifier,
        A,
        values_A,
        B,
        values_B,
    )

    # Settle channel
    web3.testing.mine(settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # A unlock's
    token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact()

    # B unlock's
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlocked pending transfers A -> B, that belong to B
    unlockable_A = get_unlocked_amount(
        secret_registry_contract,
        pending_transfers_tree_A.packed_transfers,
    )

    # Expired pending transfers A -> B, that belong to A
    expired_A = get_locked_amount(pending_transfers_tree_A.expired)

    # Unlocked pending transfers B -> A, that belong to A
    unlockable_B = get_unlocked_amount(
        secret_registry_contract,
        pending_transfers_tree_B.packed_transfers,
    )

    # Expired pending transfers B -> A, that belong to B
    expired_B = get_locked_amount(pending_transfers_tree_B.expired)

    # check that A and B both received the expected amounts
    assert balance_contract == pre_balance_contract - values_B.locked - values_A.locked
    assert balance_A == pre_balance_A + unlockable_B + expired_A
    assert balance_B == pre_balance_B + unlockable_A + expired_B


def test_unlock_twice_fails(
        web3,
        token_network,
        get_accounts,
        create_settled_channel,
        reveal_secrets,
):
    (A, B) = get_accounts(2)
    settle_timeout = 8

    # Regular channel life-cycle: open -> settle -> unlock -> open -> settle -> unlock

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
        EMPTY_MERKLE_ROOT,
        settle_timeout,
    )
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_1.packed_transfers,
    ).transact({'from': A})

    # Calling unlock twice does not work
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            B,
            A,
            pending_transfers_tree_1.packed_transfers,
        ).transact({'from': A})


def test_channel_unlock_with_a_large_expiration(
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
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(
        deposit=20,
        transferred=5,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    values_B = ChannelValues(
        deposit=30,
        transferred=40,
    )

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data with large expiration date
    pending_transfers_tree = get_pending_transfers_tree(
        web3,
        [1, 3, 5],
        [2, 4],
        settle_timeout + 100,
    )
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked = get_locked_amount(pending_transfers_tree.transfers)

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(
        channel_identifier,
        A,
        values_A,
        B,
        values_B,
    )

    # Settle channel after a "long" time
    web3.testing.mine(settle_timeout + 50)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Unlock the tokens must still work
    token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree.packed_transfers,
    ).transact()

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - values_B.locked


def test_reverse_participants_unlock(
        web3,
        token_network,
        get_accounts,
        create_settled_channel,
        reveal_secrets,
):
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
            channel_identifier,
            A,
            B,
            pending_transfers_tree_A.packed_transfers,
        ).transact({'from': A})

    # Delegate trying to unlock A's own locksroot & locked amount on behalf of A MUST fail
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            A,
            B,
            pending_transfers_tree_A.packed_transfers,
        ).transact({'from': C})

    # B trying to unlock its own locksroot & locked amount MUST fail
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            B,
            A,
            pending_transfers_tree_B.packed_transfers,
        ).transact({'from': B})

    # Delegate trying to unlock B's own locksroot & locked amount on behalf of B MUST fail
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            B,
            A,
            pending_transfers_tree_B.packed_transfers,
        ).transact({'from': B})

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            A,
            A,
            pending_transfers_tree_A.packed_transfers,
        ).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            channel_identifier,
            B,
            B,
            pending_transfers_tree_B.packed_transfers,
        ).transact({'from': B})

    # Someone trying to unlock B's locksroot & locked amount on behalf of A MUST succeed
    token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact({'from': C})

    # Someone trying to unlock A's locksroot & locked amount on behalf of B MUST succeed
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact({'from': C})


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
    (A, B) = get_accounts(2)
    settle_timeout = 8

    values_A = ChannelValues(
        deposit=20,
        transferred=5,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    values_B = ChannelValues(
        deposit=30,
        transferred=40,
    )

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, values_A.deposit, B)
    channel_deposit(channel_identifier, B, values_B.deposit, A)

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(
        web3,
        [1, 3, 5],
        [2, 4],
        settle_timeout + 100,
    )
    values_B.locksroot = pending_transfers_tree.merkle_root
    values_B.locked = get_locked_amount(pending_transfers_tree.transfers)

    # Reveal secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree.unlockable)

    close_and_update_channel(
        channel_identifier,
        A,
        values_A,
        B,
        values_B,
    )

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    call_settle(token_network, channel_identifier, A, values_A, B, values_B)

    ev_handler = event_handler(token_network)

    # Unlock the tokens
    txn_hash = token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree.packed_transfers,
    ).transact()

    unlocked_amount = get_unlocked_amount(
        secret_registry_contract,
        pending_transfers_tree.packed_transfers,
    )

    # Add event
    ev_handler.add(txn_hash, ChannelEvent.UNLOCKED, check_channel_unlocked(
        channel_identifier,
        A,
        B,
        values_B.locksroot,
        unlocked_amount,
        values_B.locked - unlocked_amount,
    ))

    # Check that event was properly emitted
    ev_handler.check()
