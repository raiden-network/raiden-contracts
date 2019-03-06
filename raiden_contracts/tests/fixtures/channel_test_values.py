from raiden_contracts.tests.utils import MAX_UINT256, ChannelValues

# We must cover the edge cases documented in
# https://github.com/raiden-network/raiden-contracts/issues/188
# The scope is to make sure that if someone uses an old balance proof, this cannot be used as
# an attack to steal tokens.
# For invalid balance proofs (created and signed with an unofficial Raiden client),
# we cannot determine and guarantee corectness. There are specific constraints that the
# Raiden client must enforce that guarantee correctness.

# For all valid last balance proofs provided we have manually constructed a suit of old balance
# proof pairs that could be used for attacks (documented edge cases).
# We will test that using old balance proofs does not result in cheating, therefore the attacker
# (participant who provides the old balance proof) must not receive more tokens than in the case
# where he provides a `valid last` balance proof.
channel_settle_test_values = [
    {
        'valid_last': (
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=20020,
                claimable_locked=3,
                unclaimable_locked=1,
            ),
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=20030,
                claimable_locked=4,
                unclaimable_locked=2,
            ),
        ),
        # participant2 provides a valid but old balance proof of participant1
        'old_last': [
            # participant2 does not send participant1's balance proof
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=0,
                claimable_locked=0,
                unclaimable_locked=0,
            ),
            # participant2 provides an old participant1 balance proof with a smaller
            # transferred amount
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=10000,
                claimable_locked=3,
                unclaimable_locked=1,
            ),
            # participant2 provides an old participant1 balance proof with a smaller
            # claimable locked amount
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=20020,
                claimable_locked=0,
                unclaimable_locked=1,
            ),
            # participant2 provides an old participant1 balance proof with a smaller
            # unclaimable locked amount
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=20020,
                claimable_locked=3,
                unclaimable_locked=0,
            ),
            # participant2 provides an old participant1 balance proof with a smaller transferred
            # & claimable locked amount
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=10000,
                claimable_locked=0,
                unclaimable_locked=1,
            ),
            # participant2 provides an old participant1 balance proof will all values smaller
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=10000,
                claimable_locked=0,
                unclaimable_locked=0,
            ),
            # participant2 provides an old participant1 balance proof, but with the same
            # transferred + claimable_locked
            # This should have the same final participant balances as the valid last balance proofs
            # locked amount cannot be bigger than the available deposit at that time
            # 18 is the maximum locked amount that can happen with valid balance proofs
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=20006,
                claimable_locked=17,
                unclaimable_locked=1,
            ),
            # participant2 provides an old participant1 balance proof, with a higher
            # unclaimable locked amount can happen if expired transfers are removed
            # from the merkle tree
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=20020,
                claimable_locked=3,
                unclaimable_locked=12,
            ),
            # participant2 provides an old participant1 balance proof with a higher
            # claimable locked amount, but lower transferred + claimable_locked
            # A higher claimable locked amount can happen even if the locked tokens are
            # eventually claimed off-chain (become transferred amount).
            # This is because we can register secrets on-chain at any point in time.
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=10020,
                claimable_locked=17,
                unclaimable_locked=1,
            ),
            # participant2 provides an old participant1 balance proof with a higher
            # unclaimable locked amount and a higher claimable locked amount but lower
            # transferred + claimable_locked
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=10020,
                claimable_locked=17,
                unclaimable_locked=10,
            ),
        ],
        # participant1 provides a valid but old participant2 balance proof
        # these examples must maintain the same order of calculating the balances
        # imposed by tranferred2 + locked2 >= transferred1 + locked1
        'last_old': [
            # participant1 provides an old participant2 balance proof with a smaller
            # transferred amount
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=20020,
                claimable_locked=4,
                unclaimable_locked=2,
            ),
            # participant1 provides an old participant2 balance proof with a smaller
            # claimable locked amount
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=20030,
                claimable_locked=0,
                unclaimable_locked=2,
            ),
            # participant1 provides an old participant2 balance proof with a smaller
            # unclaimable locked amount
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=20030,
                claimable_locked=4,
                unclaimable_locked=0,
            ),
            # participant1 provides an old participant2 balance proof with a smaller transferred
            # & claimable locked amount
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=20022,
                claimable_locked=0,
                unclaimable_locked=2,
            ),
            # participant1 provides an old participant2 balance proof will all values smaller
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=20024,
                claimable_locked=0,
                unclaimable_locked=0,
            ),
            # participant1 provides an old participant2 balance proof, but with the same
            # transferred + claimable_locked
            # This should have the same final participant balances as the valid last balance proofs
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=19994,
                claimable_locked=40,
                unclaimable_locked=2,
            ),
            # participant1 provides an old participant2 balance proof, with a higher
            # unclaimable locked amount
            # can happen if expired transfers are removed from the merkle tree
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=20030,
                claimable_locked=4,
                unclaimable_locked=20,
            ),
            # participant1 provides an old participant2 balance proof with a higher
            # claimable locked amount,
            # but lower transferred + claimable_locked
            # A higher claimable locked amount can happen even if the locked tokens are
            # eventually claimed off-chain (become transferred amount).
            # This is because we can register secrets on-chain at any point in time.
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=19990,
                claimable_locked=40,
                unclaimable_locked=2,
            ),
            # participant1 provides an old participant2 balance proof with a higher
            # unclaimable locked amount and a higher claimable locked amount but lower
            # transferred + claimable_locked
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=19990,
                claimable_locked=40,
                unclaimable_locked=10,
            ),
        ],
    },
    {
        # neither participants provide balance proofs
        'valid_last': (
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=0,
                claimable_locked=0,
                unclaimable_locked=0,
            ),
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=0,
                claimable_locked=0,
                unclaimable_locked=0,
            ),
        ),
    },
    {
        # both balance proofs provided are valid
        'valid_last': (
            ChannelValues(
                deposit=35,
                withdrawn=5,
                transferred=20,
                claimable_locked=4,
                unclaimable_locked=0,
            ),
            ChannelValues(
                deposit=40,
                withdrawn=10,
                transferred=30,
                claimable_locked=4,
                unclaimable_locked=2,
            ),
        ),
    },
    {
        # Participants have withdrawn all their tokens already
        'valid_last': (
            ChannelValues(
                deposit=5,
                withdrawn=15,
                transferred=20,
                claimable_locked=0,
                unclaimable_locked=0,
            ),
            ChannelValues(
                deposit=20,
                withdrawn=10,
                transferred=30,
                claimable_locked=0,
                unclaimable_locked=0,
            ),
        ),
    },
    {
        # Participants have withdrawn all their finalized transfer tokens except locked,
        'valid_last': (
            ChannelValues(
                deposit=5,
                withdrawn=5,
                transferred=20,
                claimable_locked=4,
                unclaimable_locked=1,
            ),
            ChannelValues(
                deposit=25,
                withdrawn=5,
                transferred=30,
                claimable_locked=2,
                unclaimable_locked=3,
            ),
        ),
    },
]

channel_settle_invalid_test_values = [
    (
        # bigger locked amounts than what remains in the contract after settlement
        ChannelValues(
            deposit=35,
            withdrawn=5,
            transferred=20020,
            claimable_locked=30000000,
            unclaimable_locked=10000000,
        ),
        ChannelValues(
            deposit=40,
            withdrawn=10,
            transferred=20030,
            claimable_locked=10000000,
            unclaimable_locked=40000000,
        ),
    ),
    # participant2 does not provide a balance proof + locked amount too big
    (
        ChannelValues(
            deposit=35,
            withdrawn=5,
            transferred=0,
            claimable_locked=0,
            unclaimable_locked=0,
        ),
        ChannelValues(
            deposit=40,
            withdrawn=10,
            transferred=30,
            claimable_locked=4,
            unclaimable_locked=2,
        ),
    ),
    # Participants have withdrawn all their finalized transfer tokens already,
    # only locked tokens left
    (
        ChannelValues(
            deposit=5,
            withdrawn=10,
            transferred=20,
            claimable_locked=4,
            unclaimable_locked=1,
        ),
        ChannelValues(
            deposit=20,
            withdrawn=5,
            transferred=30,
            claimable_locked=2,
            unclaimable_locked=3,
        ),
    ),
    (
        ChannelValues(
            deposit=5,
            withdrawn=5,
            transferred=20,
            claimable_locked=0,
            unclaimable_locked=0,
        ),
        ChannelValues(
            deposit=10,
            withdrawn=10,
            transferred=30,
            claimable_locked=0,
            unclaimable_locked=0,
        ),
    ),
    (
        ChannelValues(
            deposit=5,
            withdrawn=5,
            transferred=20,
            claimable_locked=1,
            unclaimable_locked=3,
        ),
        ChannelValues(
            deposit=10,
            withdrawn=10,
            transferred=30,
            claimable_locked=2,
            unclaimable_locked=4,
        ),
    ),
    # overflow on transferred amounts
    (
        ChannelValues(
            deposit=35,
            withdrawn=5,
            transferred=MAX_UINT256 - 15,
            claimable_locked=3,
            unclaimable_locked=1,
        ),
        ChannelValues(
            deposit=40,
            withdrawn=10,
            transferred=MAX_UINT256 - 5,
            claimable_locked=5,
            unclaimable_locked=1,
        ),
    ),
    # overflow on transferred amount
    (
        ChannelValues(
            deposit=35,
            withdrawn=5,
            transferred=0,
            claimable_locked=4,
            unclaimable_locked=0,
        ),
        ChannelValues(
            deposit=40,
            withdrawn=10,
            transferred=MAX_UINT256 - 5,
            claimable_locked=0,
            unclaimable_locked=6,
        ),
    ),
    # overflow on transferred amount
    (
        ChannelValues(
            deposit=40,
            withdrawn=10,
            transferred=0,
            claimable_locked=6,
            unclaimable_locked=0,
        ),
        ChannelValues(
            deposit=35,
            withdrawn=5,
            transferred=MAX_UINT256 - 15,
            claimable_locked=1,
            unclaimable_locked=3,
        ),
    ),
    # overflow on transferred amount
    (
        ChannelValues(
            deposit=35,
            withdrawn=5,
            transferred=20020,
            claimable_locked=200000,
            unclaimable_locked=200,
        ),
        ChannelValues(
            deposit=40,
            withdrawn=10,
            transferred=MAX_UINT256 - 5,
            claimable_locked=0,
            unclaimable_locked=0,
        ),
    ),
    # overflow on transferred amount, overflow on netted transfer + deposit
    (
        ChannelValues(
            deposit=35,
            withdrawn=5,
            transferred=20,
            claimable_locked=200,
            unclaimable_locked=200000,
        ),
        ChannelValues(
            deposit=40,
            withdrawn=10,
            transferred=MAX_UINT256 - 5,
            claimable_locked=0,
            unclaimable_locked=0,
        ),
    ),
]
