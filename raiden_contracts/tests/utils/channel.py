from collections import namedtuple
from copy import deepcopy
from typing import Tuple

from eth_typing import HexAddress
from eth_utils import encode_hex, keccak, to_canonical_address
from web3.contract import Contract

from raiden_contracts.constants import LOCKSROOT_OF_NO_LOCKS
from raiden_contracts.tests.utils.constants import EMPTY_ADDITIONAL_HASH, UINT256_MAX

SettlementValues = namedtuple(
    "SettlementValues",
    ["participant1_balance", "participant2_balance", "participant1_locked", "participant2_locked"],
)


class LockedAmounts:
    def __init__(self, claimable_locked: int = 0, unclaimable_locked: int = 0):
        self.claimable_locked = claimable_locked
        self.unclaimable_locked = unclaimable_locked

    @property
    def locked(self) -> int:
        return self.claimable_locked + self.unclaimable_locked


ZERO_LOCKED_VALUES = LockedAmounts()


class ChannelValues:
    def __init__(
        self,
        deposit: int = 0,
        withdrawn: int = 0,
        nonce: int = 0,
        transferred: int = 0,
        locked_amounts: LockedAmounts = ZERO_LOCKED_VALUES,
        locksroot: bytes = LOCKSROOT_OF_NO_LOCKS,
        additional_hash: bytes = EMPTY_ADDITIONAL_HASH,
    ):
        self.deposit = deposit
        self.withdrawn = withdrawn
        self.nonce = nonce
        self.transferred = transferred
        # deepcopy is necessary because later some elements are incremented in-place.
        self.locked_amounts = deepcopy(locked_amounts)
        self.locksroot = locksroot
        self.additional_hash = additional_hash

    def __repr__(self) -> str:
        return (
            f"ChannelValues deposit:{self.deposit} withdrawn:{self.withdrawn} "
            f"transferred:{self.transferred} claimable_"
            f"locked:{self.locked_amounts.claimable_locked} "
            f"unclaimable_locked:{self.locked_amounts.unclaimable_locked} "
            f"locked:{self.locked_amounts.locked} "
            f"locksroot:{encode_hex(self.locksroot)}"
        )


def get_participant_available_balance(
    participant1: ChannelValues, participant2: ChannelValues
) -> int:
    """ Returns the available balance for participant1

    The available balance is used in the Raiden client, in order to check if a
    participant is able to make transfers or not.
    """
    return (
        participant1.deposit
        + participant2.transferred
        - participant1.withdrawn
        - participant1.transferred
        - participant1.locked_amounts.locked
    )


def are_balance_proofs_valid(participant1: ChannelValues, participant2: ChannelValues) -> bool:
    """ Checks if balance proofs are valid or could have been valid at a certain point in time

    Balance proof constraints are detailed in
    https://github.com/raiden-network/raiden-contracts/issues/188#issuecomment-404752095
    """
    participant1_available_balance = get_participant_available_balance(participant1, participant2)
    participant2_available_balance = get_participant_available_balance(participant2, participant1)

    total_available_deposit = get_total_available_deposit(participant1, participant2)

    return (
        0 <= participant1.transferred <= UINT256_MAX
        and 0 <= participant2.transferred <= UINT256_MAX
        and 0 <= participant1.locked_amounts.locked <= UINT256_MAX
        and 0 <= participant2.locked_amounts.locked <= UINT256_MAX
        and participant1.transferred + participant1.locked_amounts.locked <= UINT256_MAX
        and participant2.transferred + participant2.locked_amounts.locked <= UINT256_MAX
        and 0 <= participant1_available_balance <= total_available_deposit
        and 0 <= participant2_available_balance <= total_available_deposit
        and total_available_deposit <= UINT256_MAX
        and participant1.locked_amounts.locked <= participant1_available_balance
        and participant2.locked_amounts.locked <= participant2_available_balance
    )


def were_balance_proofs_valid(participant1: ChannelValues, participant2: ChannelValues) -> bool:
    """ Checks if balance proofs were ever valid. """
    deposit = participant1.deposit + participant2.deposit

    # Regardless of issuance time, the locked amount must be smaller than the
    # total channel deposit.
    return (
        participant1.locked_amounts.locked <= deposit
        and participant2.locked_amounts.locked <= deposit
    )


def is_balance_proof_old(participant1: ChannelValues, participant2: ChannelValues) -> bool:
    """ Checks if balance proofs are valid, with at least one old. """
    assert were_balance_proofs_valid(participant1, participant2)

    total_available_deposit = get_total_available_deposit(participant1, participant2)

    (participant1_balance, participant2_balance) = get_expected_after_settlement_unlock_amounts(
        participant1, participant2
    )

    # Valid last balance proofs should ensure the following equality:
    if participant1_balance + participant2_balance == total_available_deposit:
        return False

    return True


def get_settlement_amounts(
    participant1: ChannelValues, participant2: ChannelValues
) -> SettlementValues:
    """ Settlement algorithm

    Calculates the token amounts to be transferred to the channel participants when
    a channel is settled.

    !!! Don't change this unless you really know what you are doing.
    """
    total_available_deposit = get_total_available_deposit(participant1, participant2)
    participant1_max_transferred = min(
        participant1.transferred + participant1.locked_amounts.locked, UINT256_MAX
    )
    participant2_max_transferred = min(
        participant2.transferred + participant2.locked_amounts.locked, UINT256_MAX
    )
    participant1_max_amount_receivable = (
        participant1.deposit
        + participant2_max_transferred
        - participant1_max_transferred
        - participant1.withdrawn
    )

    participant1_max_amount_receivable = max(participant1_max_amount_receivable, 0)
    participant1_max_amount_receivable = min(
        participant1_max_amount_receivable, total_available_deposit
    )
    participant2_max_amount_receivable = (
        total_available_deposit - participant1_max_amount_receivable
    )

    participant2_locked = min(
        participant2.locked_amounts.locked, participant1_max_amount_receivable
    )
    participant1_locked = min(
        participant1.locked_amounts.locked, participant2_max_amount_receivable
    )

    participant1_amount = participant1_max_amount_receivable - participant2_locked
    participant2_amount = participant2_max_amount_receivable - participant1_locked

    assert total_available_deposit == (
        participant1_amount + participant2_amount + participant1_locked + participant2_locked
    )

    return SettlementValues(
        participant1_balance=participant1_amount,
        participant2_balance=participant2_amount,
        participant1_locked=participant1_locked,
        participant2_locked=participant2_locked,
    )


def get_expected_after_settlement_unlock_amounts(
    participant1: ChannelValues, participant2: ChannelValues
) -> Tuple[int, int]:
    """ Get expected balances after the channel is settled and all locks are unlocked

    We make the assumption that both balance proofs provided are valid, meaning that both
    participants' balance proofs are the last known balance proofs from the channel.
    """
    participant1_balance = (
        participant1.deposit
        - participant1.withdrawn
        + participant2.transferred
        - participant1.transferred
        + participant2.locked_amounts.claimable_locked
        - participant1.locked_amounts.claimable_locked
    )
    participant2_balance = (
        participant2.deposit
        - participant2.withdrawn
        + participant1.transferred
        - participant2.transferred
        + participant1.locked_amounts.claimable_locked
        - participant2.locked_amounts.claimable_locked
    )
    return (participant1_balance, participant2_balance)


def failsafe_add(a: int, b: int) -> int:
    """
    Function to compute the settlement amounts w.r.t. MAX_UINT, as it happens in the contract
    :param a: Addend
    :param b: Addend
    :return: sum, if a+b mod MAX_UINT+1 would not overflow else: MAX_UINT256
    """
    a = a % (UINT256_MAX + 1)
    b = b % (UINT256_MAX + 1)
    ret = (a + b) % (UINT256_MAX + 1)
    if ret >= a:
        return ret
    else:
        return UINT256_MAX


def failsafe_sub(a: int, b: int) -> Tuple[int, int]:
    """
    Function to compute the settlement amounts w.r.t. MAX_UINT, as it happens in the contract
    :param a: Minuend
    :param b: Subtrahend
    :return: tuple(difference, Subtrahend) if a-b mod MAX_UINT+1 would not underflow
     else: tuple(0, Minuend)
    """
    a = a % (UINT256_MAX + 1)
    b = b % (UINT256_MAX + 1)
    return (a - b, b) if a > b else (0, a)


def get_onchain_settlement_amounts(
    participant1: ChannelValues, participant2: ChannelValues
) -> SettlementValues:
    """ Settlement algorithm

    Calculates the token amounts to be transferred to the channel participants when
    a channel is settled.

    !!! Don't change this unless you really know what you are doing.
    """

    assert (
        participant2.transferred + participant2.locked_amounts.locked
        >= participant1.transferred + participant1.locked_amounts.locked
    )

    total_available_deposit = get_total_available_deposit(participant1, participant2)

    # we assume that total_available_deposit does not overflow in settleChannel
    assert total_available_deposit <= UINT256_MAX

    participant1_max_transferred = failsafe_add(
        participant1.transferred, participant1.locked_amounts.locked
    )
    participant2_max_transferred = failsafe_add(
        participant2.transferred, participant2.locked_amounts.locked
    )

    assert participant1_max_transferred <= UINT256_MAX
    assert participant2_max_transferred <= UINT256_MAX

    participant1_net_max_transferred = participant2_max_transferred - participant1_max_transferred

    participant1_max_amount = failsafe_add(participant1_net_max_transferred, participant1.deposit)
    (participant1_max_amount, _) = failsafe_sub(participant1_max_amount, participant1.withdrawn)

    participant1_max_amount = min(participant1_max_amount, total_available_deposit)

    participant2_max_amount = total_available_deposit - participant1_max_amount

    (participant1_amount, participant2_locked_amount) = failsafe_sub(
        participant1_max_amount, participant2.locked_amounts.locked
    )

    (participant2_amount, participant1_locked_amount) = failsafe_sub(
        participant2_max_amount, participant1.locked_amounts.locked
    )

    assert total_available_deposit == (
        participant1_amount
        + participant2_amount
        + participant1_locked_amount
        + participant2_locked_amount
    )

    return SettlementValues(
        participant1_balance=participant1_amount,
        participant2_balance=participant2_amount,
        participant1_locked=participant1_locked_amount,
        participant2_locked=participant2_locked_amount,
    )


def get_total_available_deposit(participant1: ChannelValues, participant2: ChannelValues) -> int:
    total_available_deposit = (
        participant1.deposit
        + participant2.deposit
        - participant1.withdrawn
        - participant2.withdrawn
    )
    return total_available_deposit


def get_unlocked_amount(secret_registry: Contract, packed_locks: bytes) -> int:
    unlocked_amount = 0

    for i in range(0, len(packed_locks), 96):
        lock = packed_locks[i : (i + 96)]
        expiration_block = int.from_bytes(lock[0:32], byteorder="big")
        locked_amount = int.from_bytes(lock[32:64], byteorder="big")
        secrethash = lock[64:96]

        reveal_block = secret_registry.functions.getSecretRevealBlockHeight(secrethash).call()
        if 0 < reveal_block < expiration_block:
            unlocked_amount += locked_amount
    return unlocked_amount


def get_participants_hash(A: HexAddress, B: HexAddress) -> bytes:
    A_canonical = to_canonical_address(A)
    B_canonical = to_canonical_address(B)
    if A_canonical == B_canonical:
        raise ValueError("get_participants_hash got the same address twice")
    return (
        keccak(A_canonical + B_canonical)
        if A_canonical < B_canonical
        else keccak(B_canonical + A_canonical)
    )
