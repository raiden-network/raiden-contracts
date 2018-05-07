from raiden_contracts.utils.config import E_CHANNEL_UNLOCKED
from raiden_contracts.utils.events import check_channel_unlocked
from .utils import (
    get_pending_transfers_tree,
    get_unlocked_amount,
    get_locked_amount
)
from raiden_contracts.utils.merkle import get_merkle_root, EMPTY_MERKLE_ROOT
from .fixtures.config import fake_hex


def test_merkle_root_0_items(
        unlock_test
):
    (locksroot, unlocked_amount) = unlock_test.call().getMerkleRootAndUnlockedAmountPublic(b'')
    assert locksroot == EMPTY_MERKLE_ROOT
    assert unlocked_amount == 0


def test_merkle_root_1_item_unlockable(
        web3,
        get_accounts,
        unlock_test,
        secret_registry
):
    A = get_accounts(1)[0]
    pending_transfers_tree = get_pending_transfers_tree(web3, [6])

    secret_registry.transact({'from': A}).registerSecret(
        pending_transfers_tree.unlockable[0][3]
    )
    assert secret_registry.call().getSecretRevealBlockHeight(
        pending_transfers_tree.unlockable[0][2]
    ) == web3.eth.blockNumber

    (locksroot, unlocked_amount) = unlock_test.call().getMerkleRootAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    )

    merkle_root = get_merkle_root(pending_transfers_tree.merkle_tree)
    assert locksroot == merkle_root
    assert unlocked_amount == 6


def test_merkle_root(
        web3,
        get_accounts,
        unlock_test,
        secret_registry
):
    (A, B) = get_accounts(2)
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 8, 3])

    for lock in pending_transfers_tree.unlockable:
        secret_registry.transact({'from': A}).registerSecret(lock[3])
        assert secret_registry.call().getSecretRevealBlockHeight(lock[2]) == web3.eth.blockNumber

    (locksroot, unlocked_amount) = unlock_test.call().getMerkleRootAndUnlockedAmountPublic(
        pending_transfers_tree.packed_transfers
    )
    merkle_root = get_merkle_root(pending_transfers_tree.merkle_tree)

    assert locksroot == merkle_root
    assert unlocked_amount == 9


def test_channel_unlock(
        web3,
        custom_token,
        token_network,
        secret_registry,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
        event_handler
):
    (A, B) = get_accounts(2)
    settle_timeout = 8
    deposit_A = 20
    deposit_B = 30
    additional_hash = fake_hex(32, '02')
    locksroot1 = fake_hex(32, '00')
    locked_amount1 = 0

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, deposit_A, B)
    channel_deposit(B, deposit_B, A)

    # Mock pending transfers data
    pending_transfers_tree = get_pending_transfers_tree(web3, [1, 3, 5], [2, 4], settle_timeout)
    locksroot_bytes = get_merkle_root(pending_transfers_tree.merkle_tree)
    locksroot2 = '0x' + locksroot_bytes.hex()
    locked_amount2 = get_locked_amount(pending_transfers_tree.transfers)

    # Create balance proofs
    balance_proof_A = create_balance_proof(
        channel_identifier,
        A, 10, locked_amount1, 5,
        locksroot1, additional_hash
    )
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B, 5, locked_amount2, 3,
        locksroot2, additional_hash
    )
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    # Reveal secrets before settlement window ends
    for lock in pending_transfers_tree.unlockable:
        secret_registry.transact({'from': A}).registerSecret(lock[3])
        assert secret_registry.call().getSecretRevealBlockHeight(lock[2]) == web3.eth.blockNumber

    # Close channel and update balance proofs
    token_network.transact({'from': A}).closeChannel(B, *balance_proof_B)
    token_network.transact({'from': B}).updateNonClosingBalanceProof(
        A, B,
        *balance_proof_A,
        balance_proof_update_signature_B
    )

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    # Settle the channel
    token_network.transact({'from': A}).settleChannel(
        A, 10, locked_amount1, locksroot1,
        B, 5, locked_amount2, locksroot2
    )

    pre_balance_A = custom_token.call().balanceOf(A)
    pre_balance_B = custom_token.call().balanceOf(B)
    pre_balance_contract = custom_token.call().balanceOf(token_network.address)

    # TODO to be moved to a separate test
    ev_handler = event_handler(token_network)

    # Unlock the tokens
    txn_hash = token_network.transact().unlock(
        A,
        B,
        pending_transfers_tree.packed_transfers
    )

    unlocked_amount = get_unlocked_amount(secret_registry, pending_transfers_tree.packed_transfers)

    balance_A = custom_token.call().balanceOf(A)
    balance_B = custom_token.call().balanceOf(B)
    balance_contract = custom_token.call().balanceOf(token_network.address)
    assert balance_A == pre_balance_A + 9
    assert balance_B == pre_balance_B + 6
    assert balance_contract == pre_balance_contract - locked_amount2

    # TODO to be moved to a separate test
    ev_handler.add(txn_hash, E_CHANNEL_UNLOCKED, check_channel_unlocked(
        channel_identifier,
        A,
        unlocked_amount,
        locked_amount2 - unlocked_amount
    ))
    ev_handler.check()
