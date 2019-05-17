from collections import namedtuple
from functools import reduce
from hashlib import sha256
from os import urandom
from random import randint

from eth_abi import encode_abi
from web3 import Web3

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN
from raiden_contracts.utils.merkle import compute_merkle_tree, get_merkle_root

PendingTransfersTree = namedtuple(
    "PendingTransfersTree",
    [
        "transfers",
        "unlockable",
        "expired",
        "packed_transfers",
        "merkle_tree",
        "merkle_root",
        "locked_amount",
    ],
)


def get_pending_transfers_tree(
    web3,
    unlockable_amounts=None,
    expired_amounts=None,
    min_expiration_delta=None,
    max_expiration_delta=None,
    unlockable_amount=None,
    expired_amount=None,
):
    if isinstance(unlockable_amount, int):
        unlockable_amounts = get_random_values_for_sum(unlockable_amount)
    if isinstance(expired_amount, int):
        expired_amounts = get_random_values_for_sum(expired_amount)

    types = ["uint256", "uint256", "bytes32"]
    packed_transfers = b""
    (unlockable_locks, expired_locks) = get_pending_transfers(
        web3=web3,
        unlockable_amounts=unlockable_amounts,
        expired_amounts=expired_amounts,
        min_expiration_delta=min_expiration_delta,
        max_expiration_delta=max_expiration_delta,
    )

    pending_transfers = unlockable_locks + expired_locks

    hashed_pending_transfers = [
        Web3.soliditySha3(types, transfer_data[:-1])  # pylint: disable=E1120
        for transfer_data in pending_transfers
    ]

    if len(pending_transfers) > 0:
        hashed_pending_transfers, pending_transfers = zip(
            *sorted(zip(hashed_pending_transfers, pending_transfers))
        )
        pending_transfers = list(pending_transfers)
        packed_transfers = get_packed_transfers(pending_transfers=pending_transfers, types=types)

    merkle_tree = compute_merkle_tree(hashed_pending_transfers)
    merkle_root = get_merkle_root(merkle_tree)
    locked_amount = get_locked_amount(pending_transfers)

    return PendingTransfersTree(
        transfers=pending_transfers,
        unlockable=unlockable_locks,
        expired=expired_locks,
        packed_transfers=packed_transfers,
        merkle_tree=merkle_tree,
        merkle_root=merkle_root,
        locked_amount=locked_amount,
    )


def get_pending_transfers(
    web3, unlockable_amounts, expired_amounts, min_expiration_delta, max_expiration_delta
):
    current_block = web3.eth.blockNumber
    if expired_amounts is None:
        expired_amounts = []
    min_expiration_delta = min_expiration_delta or (len(unlockable_amounts) + 1)
    max_expiration_delta = max_expiration_delta or (min_expiration_delta + TEST_SETTLE_TIMEOUT_MIN)
    unlockable_locks = [
        [
            current_block + randint(min_expiration_delta, max_expiration_delta),
            amount,
            *random_secret(),
        ]
        for amount in unlockable_amounts
    ]
    expired_locks = [[current_block, amount, *random_secret()] for amount in expired_amounts]
    return (unlockable_locks, expired_locks)


def get_packed_transfers(pending_transfers, types):
    packed_transfers = [encode_abi(types, x[:-1]) for x in pending_transfers]
    return reduce((lambda x, y: x + y), packed_transfers)


def get_locked_amount(pending_transfers):
    return reduce((lambda x, y: x + y[1]), pending_transfers, 0)


def random_secret():
    secret = urandom(32)
    hasher = sha256(secret)
    return (hasher.digest(), secret)


def get_random_values_for_sum(values_sum):
    amount = 0
    values = []
    while amount < values_sum:
        value = randint(1, values_sum - amount)
        values.append(value)
        amount += value
    return values
