import os
import random
from functools import reduce
from collections import namedtuple
from web3 import Web3
from raiden_contracts.utils.config import SETTLE_TIMEOUT_MIN
from raiden_contracts.utils.merkle import compute_merkle_tree, get_merkle_root
from eth_abi import encode_abi


MAX_UINT256 = 2 ** 256 - 1


PendingTransfersTree = namedtuple('PendingTransfersTree', [
    'transfers',
    'unlockable',
    'expired',
    'packed_transfers',
    'merkle_tree',
    'merkle_root',
    'locked_amount'
])


def random_secret():
    secret = os.urandom(32)
    return (Web3.soliditySha3(['bytes32'], [secret]), secret)


def get_pending_transfers(
        web3,
        unlockable_amounts,
        expired_amounts,
        min_expiration_delta,
        max_expiration_delta
):
    current_block = web3.eth.blockNumber
    min_expiration_delta = min_expiration_delta or (len(unlockable_amounts) + 1)
    max_expiration_delta = max_expiration_delta or (min_expiration_delta + SETTLE_TIMEOUT_MIN)
    unlockable_locks = [
        [
            current_block + random.randint(min_expiration_delta, max_expiration_delta),
            amount,
            *random_secret()
        ]
        for amount in unlockable_amounts
    ]
    expired_locks = [
        [current_block, amount, *random_secret()]
        for amount in expired_amounts
    ]
    return (unlockable_locks, expired_locks)


def get_pending_transfers_tree(
        web3,
        unlockable_amounts=[],
        expired_amounts=[],
        min_expiration_delta=None,
        max_expiration_delta=None
):
    types = ['uint256', 'uint256', 'bytes32']
    (unlockable_locks, expired_locks) = get_pending_transfers(
        web3,
        unlockable_amounts,
        expired_amounts,
        min_expiration_delta,
        max_expiration_delta
    )

    pending_transfers = unlockable_locks + expired_locks

    hashed_pending_transfers = [
        Web3.soliditySha3(types, transfer_data[:-1])
        for transfer_data in pending_transfers
    ]

    hashed_pending_transfers, pending_transfers = zip(*sorted(zip(
        hashed_pending_transfers,
        pending_transfers
    )))

    merkle_tree = compute_merkle_tree(hashed_pending_transfers)
    merkle_root = get_merkle_root(merkle_tree)
    merkle_root = '0x' + merkle_root.hex()
    packed_transfers = get_packed_transfers(pending_transfers, types)
    locked_amount = get_locked_amount(pending_transfers)

    return PendingTransfersTree(
        transfers=pending_transfers,
        unlockable=unlockable_locks,
        expired=expired_locks,
        packed_transfers=packed_transfers,
        merkle_tree=merkle_tree,
        merkle_root=merkle_root,
        locked_amount=locked_amount
    )


def get_packed_transfers(pending_transfers, types):
    packed_transfers = [encode_abi(types, x[:-1]) for x in pending_transfers]
    return reduce((lambda x, y: x + y), packed_transfers)


def get_settlement_amounts(
        participant1,
        participant2
):
    """ Settlement algorithm

    Calculates the token amounts to be transferred to the channel participants when
    a channel is settled
    """
    total_available_deposit = (
        participant1.deposit +
        participant2.deposit -
        participant1.withdrawn -
        participant2.withdrawn
    )
    participant1_amount = (
        participant1.deposit +
        participant2.transferred -
        participant1.withdrawn -
        participant1.transferred
    )
    participant1_amount = min(participant1_amount, total_available_deposit)
    participant1_amount = max(participant1_amount, 0)
    participant2_amount = total_available_deposit - participant1_amount

    participant1_amount = max(participant1_amount - participant1.locked, 0)
    participant2_amount = max(participant2_amount - participant2.locked, 0)

    return (participant1_amount, participant2_amount, participant1.locked + participant2.locked)


def get_unlocked_amount(secret_registry, merkle_tree_leaves):
    unlocked_amount = 0

    for i in range(0, len(merkle_tree_leaves), 96):
        lock = merkle_tree_leaves[i:(i + 96)]
        expiration_block = int.from_bytes(lock[0:32], byteorder='big')
        locked_amount = int.from_bytes(lock[32:64], byteorder='big')
        secrethash = lock[64:96]

        reveal_block = secret_registry.call().getSecretRevealBlockHeight(secrethash)
        if reveal_block > 0 and reveal_block < expiration_block:
            unlocked_amount += locked_amount
    return unlocked_amount


def get_locked_amount(pending_transfers):
    return reduce((lambda x, y: x + y[1]), pending_transfers, 0)
