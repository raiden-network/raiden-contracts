from functools import reduce
from hashlib import sha256
from os import urandom
from random import randint
from typing import Collection, Iterable, List, NamedTuple, Optional, Tuple

from eth_abi import encode_abi
from eth_utils import keccak
from web3 import Web3

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN

PendingTransfersTree = NamedTuple(
    "PendingTransfersTree",
    [
        ("transfers", List[List]),
        ("unlockable", List[List]),
        ("expired", List[List]),
        ("packed_transfers", bytes),
        ("hash_of_packed_transfers", bytes),
        ("locked_amount", int),
    ],
)


def get_pending_transfers_tree_with_generated_lists(
    web3: Web3,
    unlockable_amount: int,
    expired_amount: int,
    min_expiration_delta: Optional[int] = None,
    max_expiration_delta: Optional[int] = None,
) -> PendingTransfersTree:
    return get_pending_transfers_tree(
        web3=web3,
        unlockable_amounts=get_random_values_for_sum(unlockable_amount),
        expired_amounts=get_random_values_for_sum(expired_amount),
        min_expiration_delta=min_expiration_delta,
        max_expiration_delta=max_expiration_delta,
    )


def get_pending_transfers_tree(
    web3: Web3,
    unlockable_amounts: Collection[int],
    expired_amounts: Collection[int],
    min_expiration_delta: Optional[int] = None,
    max_expiration_delta: Optional[int] = None,
) -> PendingTransfersTree:
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
        Web3.solidityKeccak(types, transfer_data[:-1])  # pylint: disable=E1120
        for transfer_data in pending_transfers
    ]

    if len(pending_transfers) > 0:
        hashed_pending_transfers, pending_transfers = zip(
            *sorted(zip(hashed_pending_transfers, pending_transfers))
        )
        pending_transfers = list(pending_transfers)
        packed_transfers = get_packed_transfers(pending_transfers=pending_transfers, types=types)

    locked_amount = get_locked_amount(pending_transfers)

    return PendingTransfersTree(
        transfers=pending_transfers,
        unlockable=unlockable_locks,
        expired=expired_locks,
        packed_transfers=packed_transfers,
        hash_of_packed_transfers=keccak(packed_transfers),
        locked_amount=locked_amount,
    )


def get_pending_transfers(
    web3: Web3,
    unlockable_amounts: Collection[int],
    expired_amounts: Iterable[int],
    min_expiration_delta: Optional[int],
    max_expiration_delta: Optional[int],
) -> Tuple:
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


def get_packed_transfers(pending_transfers: Collection, types: List) -> bytes:
    packed_transfers: List[bytes] = [encode_abi(types, x[:-1]) for x in pending_transfers]
    return reduce((lambda x, y: x + y), packed_transfers)


def get_locked_amount(pending_transfers: List) -> int:
    return reduce((lambda x, y: x + y[1]), pending_transfers, 0)


def random_secret() -> Tuple:
    secret = urandom(32)
    hasher = sha256(secret)
    return (hasher.digest(), secret)


def get_random_values_for_sum(values_sum: int) -> List[int]:
    amount = 0
    values = []
    while amount < values_sum:
        value = randint(1, values_sum - amount)
        values.append(value)
        amount += value
    return values
