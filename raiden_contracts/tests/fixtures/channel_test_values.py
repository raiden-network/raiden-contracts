from raiden_contracts.tests.utils import MAX_UINT256, ChannelValues


channel_settle_test_values = [
    # both balance proofs provided are valid
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=20020, locked=4),
        ChannelValues(deposit=40, withdrawn=10, transferred=20030, locked=6),
    ),
    # participant2 does not provide a balance proof, locked amount ok
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=0, locked=0),
        ChannelValues(deposit=40, withdrawn=10, transferred=20030, locked=0),
    ),
    # participant2 does not provide a balance proof + bigger locked amount
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=0),
        ChannelValues(deposit=35, withdrawn=5, transferred=20020, locked=4),
    ),
    # neither participants provide balance proofs
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=0),
        ChannelValues(deposit=35, withdrawn=5, transferred=0, locked=0),
    ),
    # bigger locked amounts than what remains in the contract after settlement
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=20020, locked=40000000),
        ChannelValues(deposit=40, withdrawn=10, transferred=20030, locked=50000000),
    ),
    # both balance proofs provided are valid
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=20, locked=4),
        ChannelValues(deposit=40, withdrawn=10, transferred=30, locked=6),
    ),
    # participant2 does not provide a balance proof + locked amount too big
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=0, locked=0),
        ChannelValues(deposit=40, withdrawn=10, transferred=30, locked=6),
    ),
    # participant2 does not provide a balance proof
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=0),
        ChannelValues(deposit=35, withdrawn=5, transferred=20, locked=4),
    ),
    # all tokens have been withdrawn, locked amounts are 0
    (
        ChannelValues(deposit=5, withdrawn=5, transferred=20, locked=0),
        ChannelValues(deposit=10, withdrawn=10, transferred=30, locked=0),
    ),
    # all tokens have been withdrawn, locked amounts are > 0
    (
        ChannelValues(deposit=5, withdrawn=5, transferred=20, locked=4),
        ChannelValues(deposit=10, withdrawn=10, transferred=30, locked=6),
    ),
    # overflow on transferred amounts
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=MAX_UINT256 - 15, locked=4),
        ChannelValues(deposit=40, withdrawn=10, transferred=MAX_UINT256 - 5, locked=6),
    ),
    # overflow on transferred amount
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=0, locked=4),
        ChannelValues(deposit=40, withdrawn=10, transferred=MAX_UINT256 - 5, locked=6),
    ),
    # overflow on transferred amount
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=6),
        ChannelValues(deposit=35, withdrawn=5, transferred=MAX_UINT256 - 15, locked=4),
    ),
    # overflow on transferred amount + old balance proof
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=20020, locked=200200),
        ChannelValues(deposit=40, withdrawn=10, transferred=MAX_UINT256 - 5, locked=0),

    ),
    # overflow on transferred amount + old balance proof, overflow on netted transfer + deposit
    (
        ChannelValues(deposit=35, withdrawn=5, transferred=20, locked=200200),
        ChannelValues(deposit=40, withdrawn=10, transferred=MAX_UINT256 - 5, locked=0),
    ),
]
