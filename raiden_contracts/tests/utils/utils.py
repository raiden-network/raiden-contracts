from collections import namedtuple
from eth_utils import keccak, to_canonical_address
from raiden_contracts.tests.fixtures.config import EMPTY_LOCKSROOT, EMPTY_ADDITIONAL_HASH


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
            nonce=0,
            transferred=0,
            locked=0,
            claimable_locked=0,
            unclaimable_locked=0,
            locksroot=EMPTY_LOCKSROOT,
            additional_hash=EMPTY_ADDITIONAL_HASH,
    ):
        self.deposit = deposit
        self.withdrawn = withdrawn
        self.nonce = nonce
        self.transferred = transferred
        self.claimable_locked = claimable_locked or locked
        self.unclaimable_locked = unclaimable_locked
        self.locked = self.claimable_locked + self.unclaimable_locked or locked
        self.locksroot = locksroot
        self.additional_hash = additional_hash

    def __repr__(self):
        return (
            f'ChannelValues deposit:{self.deposit} withdrawn:{self.withdrawn} '
            f'transferred:{self.transferred} claimable_locked:{self.claimable_locked} '
            f'unclaimable_locked:{self.unclaimable_locked} '
            f'locked:{self.locked} locksroot:{self.locksroot} '
        )


def random_secret():
    secret = os.urandom(32)
    return (Web3.soliditySha3(['bytes32'], [secret]), secret)


def get_pending_transfers(
        web3,
        unlockable_amounts,
        expired_amounts,
        min_expiration_delta=0,
        max_expiration_delta=0,
):
    current_block = web3.eth.blockNumber
    min_expiration_delta = min_expiration_delta or (len(unlockable_amounts) + 1)
    max_expiration_delta = max_expiration_delta or (min_expiration_delta + TEST_SETTLE_TIMEOUT_MIN)

    unlockable_locks = [
        [
            current_block + random.randint(min_expiration_delta, max_expiration_delta),
            amount,
            *random_secret(),
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
        unlockable_amounts=None,
        expired_amounts=None,
        min_expiration_delta=None,
        max_expiration_delta=None,
        unlockable_amount=None,
        expired_amount=None,
):
    types = ['uint256', 'uint256', 'bytes32']
    if unlockable_amounts is None:
        unlockable_amounts = []
    if expired_amounts is None:
        expired_amounts = []
    if unlockable_amount is not None:
        unlockable_amounts = get_random_values_for_sum(unlockable_amount)
    if expired_amount is not None:
        expired_amounts = get_random_values_for_sum(expired_amount)

    (unlockable_locks, expired_locks) = get_pending_transfers(
        web3,
        unlockable_amounts,
        expired_amounts,
        min_expiration_delta,
        max_expiration_delta,
    )
    pending_transfers = unlockable_locks + expired_locks

    hashed_pending_transfers = [
        Web3.soliditySha3(types, transfer_data[:-1])
        for transfer_data in pending_transfers
    ]
    if len(pending_transfers) > 0:
        hashed_pending_transfers, pending_transfers = zip(*sorted(zip(
            hashed_pending_transfers,
            pending_transfers,
        )))
        packed_transfers = get_packed_transfers(pending_transfers, types)
    else:
        packed_transfers = b''

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


def get_packed_transfers(pending_transfers, types):
    packed_transfers = [encode_abi(types, x[:-1]) for x in pending_transfers]
    return reduce((lambda x, y: x + y), packed_transfers)


def get_participant_available_balance(participant1, participant2):
    """ Returns the available balance for participant1

    The available balance is used in the Raiden client, in order to check if a
    participant is able to make transfers or not.
    """
    return (
        participant1.deposit +
        participant2.transferred -
        participant1.withdrawn -
        participant1.transferred -
        participant1.locked
    )


def are_balance_proofs_valid(participant1, participant2):
    """ Checks if balance proofs are valid or could have been valid at a certain point in time """
    participant1_available_balance = get_participant_available_balance(participant1, participant2)
    participant2_available_balance = get_participant_available_balance(participant2, participant1)
    print('av balances', participant1_available_balance, participant2_available_balance)
    return (
        participant1.transferred + participant1.locked <= MAX_UINT256 and
        participant2.transferred + participant2.locked <= MAX_UINT256 and
        participant1_available_balance >= 0 and participant2_available_balance >= 0
    )


def is_balance_proof_old(participant1, participant2):
    """ Checks if balance proofs are valid, with at least one old. """
    both_valid = are_balance_proofs_valid(participant1, participant2)
    if not both_valid:
        return False

    total_available_deposit = get_total_available_deposit(participant1, participant2)

    (
        participant1_balance,
        participant2_balance,
    ) = get_expected_after_settlement_unlock_amounts(participant1, participant2)

    if participant1_balance + participant2_balance != total_available_deposit:
        return False

    return True


def get_settlement_amounts(participant1, participant2):
    """ Settlement algorithm

    Calculates the token amounts to be transferred to the channel participants when
    a channel is settled.

    !!! Don't change this unless you really know what you are doing.
    """
    total_available_deposit = get_total_available_deposit(participant1, participant2)
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


def get_expected_after_settlement_unlock_amounts(participant1, participant2):
    """ Get expected balances after the channel is settled and all locks are unlocked

    We make the assumption that both balance proofs provided are valid, meaning that both
    participants' balance proofs are the last known balance proofs from the channel.
    """
    participant1_balance = (
        participant1.deposit -
        participant1.withdrawn +
        participant2.transferred -
        participant1.transferred +
        participant2.claimable_locked -
        participant1.claimable_locked
    )
    participant2_balance = (
        participant2.deposit -
        participant2.withdrawn +
        participant1.transferred -
        participant2.transferred +
        participant1.claimable_locked -
        participant2.claimable_locked
    )
    return (participant1_balance, participant2_balance)


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

    total_available_deposit = get_total_available_deposit(participant1, participant2)

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


def get_total_available_deposit(participant1, participant2):
    total_available_deposit = (
        participant1.deposit +
        participant2.deposit -
        participant1.withdrawn -
        participant2.withdrawn
    )
    return total_available_deposit


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


def get_random_values_for_sum(values_sum):
    amount = 0
    values = []
    while amount < values_sum:
        value = random.randint(1, values_sum - amount)
        values.append(value)
        amount += value
    return values
