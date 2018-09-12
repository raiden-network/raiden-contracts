import pytest
from eth_tester.exceptions import TransactionFailed
from .utils import (
    get_pending_transfers_tree,
    get_locked_amount,
)
from raiden_contracts.tests.utils import ChannelValues
from raiden_contracts.tests.fixtures.channel import call_settle


def test_unlock_valid_valid_revealed_revealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=15,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [7, 3, 5, 10], [], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [5, 3, 5, 2], [], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # Reveal A's secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    # Reveal B's secrets before settlement window ends
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, B, values_B, A, values_A)
    # A will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment:
    # A has 25 tokens worth of pending transfers to B.
    # B has 15 tokens worth of pending transfers to A.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 10 tokens being owed by A to B
    # In this case, B also has a deposit of 5 tokens -> B can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 15
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    # There is nothing to unlock here, because B's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            A,
            B,
            pending_transfers_tree_B.packed_transfers,
        ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B unlocks A's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(A, B, values_A.locksroot).call() == 0

    # A's pending transfers have all the secrets revealed on chain
    # Therefore, all of A's locked tokens must go to B
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 15
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15


def test_unlock_valid_valid_notrevealed_revealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=15,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [], [7, 3, 5, 10], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [5, 3, 5, 2], [], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # DO NOT reveal A's pending transfers secrets
    # Reveal B's pending transfers secrets
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, B, values_B, A, values_A)
    # A will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment:
    # A has 25 tokens worth of pending transfers to B.
    # B has 15 tokens worth of pending transfers to A.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 10 tokens being owed by A to B
    # In this case, B also has a deposit of 5 tokens -> B can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 15
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    # There is nothing to unlock here, because B's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            A,
            B,
            pending_transfers_tree_B.packed_transfers,
        ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B unlocks A's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0

    # A's pending transfers DO NOT have secrets revealed on chain
    # Therefore, all of A's locked tokens must go back to A
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 15
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15


def test_unlock_valid_valid_revealed_notrevealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=15,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [7, 3, 5, 10], [], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [], [5, 3, 5, 2], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # Reveal A's pending transfers secrets
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    # DO NOT reveal B's pending transfers secrets

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, B, values_B, A, values_A)
    # A will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment:
    # A has 25 tokens worth of pending transfers to B.
    # B has 15 tokens worth of pending transfers to A.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 10 tokens being owed by A to B.
    # In this case, B also has a deposit of 5 tokens -> B can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 15
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    # There is nothing to unlock here, because B's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            A,
            B,
            pending_transfers_tree_B.packed_transfers,
        ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B unlocks A's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0

    # A's pending transfers have all the secrets revealed on chain
    # Therefore, all of A's locked tokens must go to B
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 15
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15


def test_unlock_valid_valid_notrevealed_notrevealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=15,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [], [7, 3, 5, 10], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [], [5, 3, 5, 2], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # DO NOT reveal A's pending transfers secrets
    # DO NOT reveal B's pending transfers secrets

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, B, values_B, A, values_A)
    # A will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment:
    # A has 25 tokens worth of pending transfers to B.
    # B has 15 tokens worth of pending transfers to A.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 10 tokens being owed by A to B
    # In this case, B also has a deposit of 5 tokens -> B can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 15
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    # There is nothing to unlock here, because B's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            A,
            B,
            pending_transfers_tree_B.packed_transfers,
        ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B unlocks A's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0

    # A's pending transfers DO NOT have the secrets revealed on chain
    # Therefore, all of A's locked tokens must go back to A
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 15
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15


def test_unlock_valid_valid_revealed_notrevealed_locked_smaller_than_deposit(
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
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=50,
        withdrawn=0,
        transferred=0,
        locked=15,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [7, 3, 5, 10], [], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(web3, [], [5, 3, 5, 2], settle_timeout)
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # Reveal A's pending transfers secrets
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    # DO NOT reveal B's pending transfers secrets
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, B, values_B, A, values_A)
    # State at this moment:
    # A has 25 tokens worth of pending transfers to B.
    # B has 15 tokens worth of pending transfers to A.
    # The total available deposit is 150, therefore we will have 25 + 15 tokens locked in the
    # smart contract.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 25
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 15

    # We transfer all tokens except the ones from the pending transfers.
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + values_A.deposit - 25
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + values_B.deposit - 15
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - values_A.deposit - values_B.deposit + 40

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # A unlocks B's pending transfers
    token_network.functions.unlock(
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B's pending transfer secrets have NOT been revealed on-chain, therefore the locked amount
    # goes back to B
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 15
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15

    # B unlocks A's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0

    # A's pending transfers have all the secrets revealed on chain
    # Therefore, all of A's locked tokens must go to B
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 25
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 25


def test_unlock_old_valid_revealed_revealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=100,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [7, 3, 5, 10], [], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(
        web3,
        [5, 3, 5, 2, 20, 10, 5, 5, 13, 6, 26],
        [],
        settle_timeout,
        max_expiration_delta=30,
    )
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # Reveal A's secrets before settlement window ends
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    # Reveal B's secrets before settlement window ends
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, A, values_A, B, values_B)
    # B will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment, as the balance proofs present us:
    # A has 25 tokens worth of pending transfers to B.
    # B has 100 tokens worth of pending transfers to A.
    # This can happen if A's balance proof is outdated.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 75 tokens being owed by B to A
    # In this case, A also has a deposit of 10 tokens ->  considering the total available deposit,
    # A can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.

    # The only person that might have something to loose at this point is A, in case the secrets
    # from B's pending transfers were not revealed on-chain.
    # This is not an issue, because he is the one responsible for what balance proof B has stored
    # in the smart contract and it is his responsibility to register the secrets on-chain if
    # he chooses to use this balance proof.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 15

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B's pending transfers have all the secrets revealed on chain
    # Therefore, all of B's locked tokens must go to A
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 15
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15

    # B unlocks A's pending transfers
    # There is nothing to unlock here, because A's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            B,
            A,
            pending_transfers_tree_A.packed_transfers,
        ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0


def test_unlock_old_valid_notrevealed_revealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=100,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [], [7, 3, 5, 10], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(
        web3,
        [5, 3, 5, 2, 20, 10, 5, 5, 13, 6, 26],
        [],
        settle_timeout,
        max_expiration_delta=30,
    )
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # DO NOT reveal A's pending transfers secrets
    # Reveal B's pending transfers secrets
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, A, values_A, B, values_B)
    # B will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment, as the balance proofs present us:
    # A has 25 tokens worth of pending transfers to B.
    # B has 100 tokens worth of pending transfers to A.
    # This can happen if A's balance proof is outdated.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 75 tokens being owed by B to A
    # In this case, A also has a deposit of 10 tokens ->  considering the total available deposit,
    # A can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.

    # The only person that might have something to loose at this point is A, in case the secrets
    # from B's pending transfers were not revealed on-chain.
    # This is not an issue, because he is the one responsible for what balance proof B has stored
    # in the smart contract and it is his responsibility to register the secrets on-chain if
    # he chooses to use this balance proof.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 15

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B's pending transfers have all the secrets revealed on chain
    # Therefore, all of B's locked tokens must go to A
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 15
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15

    # B unlocks A's pending transfers
    # There is nothing to unlock here, because A's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            B,
            A,
            pending_transfers_tree_A.packed_transfers,
        ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0


def test_unlock_old_valid_revealed_notrevealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=100,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [7, 3, 5, 10], [], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(
        web3,
        [],
        [5, 3, 5, 2, 20, 10, 5, 5, 13, 6, 26],
        settle_timeout,
        max_expiration_delta=30,
    )
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # Reveal A's pending transfers secrets
    reveal_secrets(A, pending_transfers_tree_A.unlockable)
    # DO NOT reveal B's pending transfers secrets

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, A, values_A, B, values_B)
    # B will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment, as the balance proofs present us:
    # A has 25 tokens worth of pending transfers to B.
    # B has 100 tokens worth of pending transfers to A.
    # This can happen if A's balance proof is outdated.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 75 tokens being owed by B to A
    # In this case, A also has a deposit of 10 tokens ->  considering the total available deposit,
    # A can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.

    # The only person that might have something to loose at this point is A, in case the secrets
    # from B's pending transfers were not revealed on-chain.
    # This is not an issue, because he is the one responsible for what balance proof B has stored
    # in the smart contract and it is his responsibility to register the secrets on-chain if
    # he chooses to use this balance proof.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 15

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B's pending transfers DO NOT have the secrets revealed on chain
    # Therefore, all of B's locked tokens must go back to B
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 15
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15

    # B unlocks A's pending transfers
    # There is nothing to unlock here, because A's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            B,
            A,
            pending_transfers_tree_A.packed_transfers,
        ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0


def test_unlock_old_valid_notrevealed_notrevealed(
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
        deposit=10,
        withdrawn=0,
        transferred=0,
        locked=25,
    )
    values_B = ChannelValues(
        deposit=5,
        withdrawn=0,
        transferred=0,
        locked=100,
    )

    # Create channel and deposit
    create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, values_A.deposit, B)
    channel_deposit(B, values_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(web3, [], [7, 3, 5, 10], settle_timeout)
    values_A.locksroot = pending_transfers_tree_A.merkle_root
    assert values_A.locked == get_locked_amount(pending_transfers_tree_A.transfers)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(
        web3,
        [],
        [5, 3, 5, 2, 20, 10, 5, 5, 13, 6, 26],
        settle_timeout,
        max_expiration_delta=30,
    )
    values_B.locksroot = pending_transfers_tree_B.merkle_root
    assert values_B.locked == get_locked_amount(pending_transfers_tree_B.transfers)

    close_and_update_channel(
        A,
        values_A,
        B,
        values_B,
    )

    # DO NOT reveal A's pending transfers secrets
    # DO NOT reveal B's pending transfers secrets

    # Settle channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, A, values_A, B, values_B)
    # B will only have 15 tokens locked in the contract, because we are bounding the transferred
    # and locked tokens to the total available deposit, which is 15 tokens.
    # State at this moment, as the balance proofs present us:
    # A has 25 tokens worth of pending transfers to B.
    # B has 100 tokens worth of pending transfers to A.
    # This can happen if A's balance proof is outdated.
    # When doing the calculations, we simplify the logic by assuming that the pending transfers
    # were finalized on-chain through a secret registration.
    # Therefore, we assume a final balance of 75 tokens being owed by B to A
    # In this case, A also has a deposit of 10 tokens ->  considering the total available deposit,
    # A can receive a max amount of 15 tokens.
    # We call it a max amount, because we don't know if the pending transfers were indeed
    # finalized or not.
    # These 15 tokens will be kept in the smart contract after settlement as a locked amount.

    # The only person that might have something to loose at this point is A, in case the secrets
    # from B's pending transfers were not revealed on-chain.
    # This is not an issue, because he is the one responsible for what balance proof B has stored
    # in the smart contract and it is his responsibility to register the secrets on-chain if
    # he chooses to use this balance proof.
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 15

    # We don't transfer anything at this point, because all tokens are locked inside the contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    # A unlocks B's pending transfers
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.unlock(
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact()
    assert token_network.functions.getParticipantLockedAmount(
        B,
        A,
        values_B.locksroot,
    ).call() == 0

    # B's pending transfers DO NOT have the secrets revealed on chain
    # Therefore, all of B's locked tokens must go back to B
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 15
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract - 15

    # B unlocks A's pending transfers
    # There is nothing to unlock here, because A's locked amount is 0
    with pytest.raises(TransactionFailed):
        token_network.functions.unlock(
            B,
            A,
            pending_transfers_tree_A.packed_transfers,
        ).transact()
    # The locked amount should have been removed from contract storage
    assert token_network.functions.getParticipantLockedAmount(
        A,
        B,
        values_A.locksroot,
    ).call() == 0
