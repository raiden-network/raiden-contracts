from collections import namedtuple


ChannelValues = namedtuple('ChannelValues', [
    'deposit',
    'withdrawn',
    'transferred',
    'locked'
])

channel_settle_test_values = [
    (
        ChannelValues(deposit=40, withdrawn=10, transferred=26, locked=6),
        ChannelValues(deposit=35, withdrawn=5, transferred=24, locked=4),
        True  # settleChannel transaction should pass
    ),
    (
        ChannelValues(deposit=10, withdrawn=10, transferred=26, locked=6),
        ChannelValues(deposit=5, withdrawn=5, transferred=24, locked=4),
        False  # settleChannel transaction should fail
    )
]
