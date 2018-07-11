from raiden_contracts.tests.utils import MAX_UINT256, ChannelValues


channel_settle_test_values = [
    # both balance proofs provided are valid
    (
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
    # participant2 does not provide a balance proof, locked amount ok
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
            transferred=20030,
            claimable_locked=0,
            unclaimable_locked=0,
        ),
    ),
    # participant2 does not provide a balance proof + bigger locked amount
    # neither participants provide balance proofs
    (
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
    # bigger locked amounts than what remains in the contract after settlement
    (
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
    # both balance proofs provided are valid
    (
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
    # participant2 does not provide a balance proof
    (
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
            transferred=20,
            claimable_locked=3,
            unclaimable_locked=1,
        ),
    ),
    # all tokens have been withdrawn, locked amounts are 0
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
    # all tokens have been withdrawn, locked amounts are > 0
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
    # overflow on transferred amount + old balance proof
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
    # overflow on transferred amount + old balance proof, overflow on netted transfer + deposit
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
