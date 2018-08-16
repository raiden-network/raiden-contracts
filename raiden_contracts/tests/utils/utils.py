from collections import namedtuple
from eth_utils import keccak, to_canonical_address


MAX_UINT256 = 2 ** 256 - 1

SettlementValues = namedtuple('SettlementValues', [
    'participant1_balance',
    'participant2_balance',
    'participant1_locked',
    'participant2_locked',
])


class ChannelValues():
    def __init__(
            self,
            deposit=0,
            withdrawn=0,
            transferred=0,
            locked=0,
            locksroot=b'',
            additional_hash=b'',
    ):
        self.deposit = deposit
        self.withdrawn = withdrawn
        self.transferred = transferred
        self.locked = locked
        self.locksroot = locksroot
        self.additional_hash = additional_hash

    def __repr__(self):
        return (
            'ChannelValues deposit:{} withdrawn:{} transferred:{} locked:{} locksroot:{}'
        ).format(
            self.deposit,
            self.withdrawn,
            self.transferred,
            self.locked,
            self.locksroot,
        )


def get_settlement_amounts(
        participant1,
        participant2,
):
    """ Settlement algorithm

    Calculates the token amounts to be transferred to the channel participants when
    a channel is settled.

    !!! Don't change this unless you really know what you are doing.
    """
    total_available_deposit = (
        participant1.deposit +
        participant2.deposit -
        participant1.withdrawn -
        participant2.withdrawn
    )
    participant1_max_transferred = min(
        participant1.transferred + participant1.locked,
        MAX_UINT256,
    )
    participant2_max_transferred = min(
        participant2.transferred + participant2.locked,
        MAX_UINT256,
    )
    participant1_max_amount_receivable = (
        participant1.deposit +
        participant2_max_transferred -
        participant1_max_transferred -
        participant1.withdrawn
    )

    participant1_max_amount_receivable = max(participant1_max_amount_receivable, 0)
    participant1_max_amount_receivable = min(
        participant1_max_amount_receivable,
        total_available_deposit,
    )
    participant2_max_amount_receivable = (
        total_available_deposit -
        participant1_max_amount_receivable
    )

    participant2_locked = min(participant2.locked, participant1_max_amount_receivable)
    participant1_locked = min(participant1.locked, participant2_max_amount_receivable)

    participant1_amount = participant1_max_amount_receivable - participant2_locked
    participant2_amount = participant2_max_amount_receivable - participant1_locked

    assert total_available_deposit == (
        participant1_amount +
        participant2_amount +
        participant1_locked +
        participant2_locked
    )

    return SettlementValues(
        participant1_balance=participant1_amount,
        participant2_balance=participant2_amount,
        participant1_locked=participant1_locked,
        participant2_locked=participant2_locked,
    )


def failsafe_add(a, b):
    """
    Function to compute the settlement amounts w.r.t. MAX_UINT, as it happens in the contract
    :param a: Addend
    :param b: Addend
    :return: sum, if a+b mod MAX_UINT+1 would not overflow else: MAX_UINT256
    """
    a = a % (MAX_UINT256 + 1)
    b = b % (MAX_UINT256 + 1)
    sum = (a + b) % (MAX_UINT256 + 1)
    if sum >= a:
        return sum
    else:
        return MAX_UINT256


def failsafe_sub(a, b):
    """
    Function to compute the settlement amounts w.r.t. MAX_UINT, as it happens in the contract
    :param a: Minuend
    :param b: Subtrahend
    :return: tuple(difference, Subtrahend) if a-b mod MAX_UINT+1 would not underflow
     else: tuple(0, Minuend)
    """
    a = a % (MAX_UINT256 + 1)
    b = b % (MAX_UINT256 + 1)
    return (a - b, b) if a > b else (0, a)


def get_onchain_settlement_amounts(
        participant1,
        participant2,
):
    """ Settlement algorithm

    Calculates the token amounts to be transferred to the channel participants when
    a channel is settled.

    !!! Don't change this unless you really know what you are doing.
    """

    assert(
        participant2.transferred + participant2.locked >=
        participant1.transferred + participant1.locked
    )

    total_available_deposit = (
        participant1.deposit +
        participant2.deposit -
        participant1.withdrawn -
        participant2.withdrawn)

    # we assume that total_available_deposit does not overflow in settleChannel
    assert total_available_deposit <= MAX_UINT256

    participant1_max_transferred = failsafe_add(participant1.transferred, participant1.locked)
    participant2_max_transferred = failsafe_add(participant2.transferred, participant2.locked)

    assert participant1_max_transferred <= MAX_UINT256
    assert participant2_max_transferred <= MAX_UINT256

    participant1_net_max_transferred = participant2_max_transferred - participant1_max_transferred

    participant1_max_amount = failsafe_add(participant1_net_max_transferred, participant1.deposit)
    (participant1_max_amount, _) = failsafe_sub(participant1_max_amount, participant1.withdrawn)

    participant1_max_amount = min(participant1_max_amount, total_available_deposit)

    participant2_max_amount = total_available_deposit - participant1_max_amount

    (participant1_amount, participant2_locked_amount) = failsafe_sub(
        participant1_max_amount,
        participant2.locked,
    )

    (participant2_amount, participant1_locked_amount) = failsafe_sub(
        participant2_max_amount,
        participant1.locked,
    )

    assert total_available_deposit == (
        participant1_amount +
        participant2_amount +
        participant1_locked_amount +
        participant2_locked_amount
    )

    return SettlementValues(
        participant1_balance=participant1_amount,
        participant2_balance=participant2_amount,
        participant1_locked=participant1_locked_amount,
        participant2_locked=participant2_locked_amount,
    )


def get_unlocked_amount(secret_registry, merkle_tree_leaves):
    unlocked_amount = 0

    for i in range(0, len(merkle_tree_leaves), 96):
        lock = merkle_tree_leaves[i:(i + 96)]
        expiration_block = int.from_bytes(lock[0:32], byteorder='big')
        locked_amount = int.from_bytes(lock[32:64], byteorder='big')
        secrethash = lock[64:96]

        reveal_block = secret_registry.functions.getSecretRevealBlockHeight(secrethash).call()
        if 0 < reveal_block < expiration_block:
            unlocked_amount += locked_amount
    return unlocked_amount


def get_participants_hash(A, B):
    A = to_canonical_address(A)
    B = to_canonical_address(B)
    return keccak(A + B) if A < B else keccak(B + A)
