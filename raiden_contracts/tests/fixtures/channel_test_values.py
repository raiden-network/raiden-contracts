class ChannelValues():
    def __init__(self, deposit=0, withdrawn=0, transferred=0, locked=0, locksroot=b''):
        self.deposit = deposit
        self.withdrawn = withdrawn
        self.transferred = transferred
        self.locked = locked
        self.locksroot = locksroot

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


channel_settle_test_values = [
    # both balance proofs provided are valid
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=20030, locked=6),
        ChannelValues(deposit=35, withdrawn=5, transferred=20020, locked=4)
    ),
    # participant1 does not provide a balance proof, locked amount ok
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=20030, locked=0),
        ChannelValues(deposit=35, withdrawn=5, transferred=0, locked=0)
    ),
    # participant2 does not provide a balance proof + bigger locked amount
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=0),
        ChannelValues(deposit=35, withdrawn=5, transferred=20020, locked=4)
    ),
    # neither participants provide balance proofs
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=0),
        ChannelValues(deposit=35, withdrawn=5, transferred=0, locked=0)
    ),
    # bigger locked amounts than what remains in the contract after settlement
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=20030, locked=50000000),
        ChannelValues(deposit=35, withdrawn=5, transferred=20020, locked=40000000)
    ),
    # both balance proofs provided are valid
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=30, locked=6),
        ChannelValues(deposit=35, withdrawn=5, transferred=20, locked=4)
    ),
    # participant1 does not provide a balance proof + locked amount too big
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=30, locked=6),
        ChannelValues(deposit=35, withdrawn=5, transferred=0, locked=0)
    ),
    # participant2 does not provide a balance proof
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=0, locked=0),
        ChannelValues(deposit=35, withdrawn=5, transferred=20, locked=4)
    ),
    # all tokens have been withdrawn, locked amounts are 0
    (
        ChannelValues(deposit=10, withdrawn=10, transferred=30, locked=0),
        ChannelValues(deposit=5, withdrawn=5, transferred=20, locked=0)
    ),
    # all tokens have been withdrawn, locked amounts are > 0
    (
        ChannelValues(deposit=10, withdrawn=10, transferred=30, locked=6),
        ChannelValues(deposit=5, withdrawn=5, transferred=20, locked=4)
    )
]
