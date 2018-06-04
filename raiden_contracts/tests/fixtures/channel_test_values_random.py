from random import randint
from sys import maxsize
from collections import namedtuple


ChannelValues = namedtuple('ChannelValues', [
    'deposit',
    'withdrawn',
    'transferred',
    'locked'
])


def channel_settle_test_values_random(n):
    return [
        (
            tuple([
                ChannelValues(
                    deposit=deposit,
                    withdrawn=withdrawn,
                    transferred=transferred,
                    locked=locked
                )
                for deposit, withdrawn, transferred, locked in
                [sorted(randint(0, maxsize) for _ in range(4)) for _ in range(n)]
            ]),
            True
        ),
        (
            tuple([
                ChannelValues(
                    deposit=deposit,
                    withdrawn=withdrawn,
                    transferred=transferred,
                    locked=locked
                )
                for withdrawn, transferred, deposit, locked in
                [sorted(randint(0, maxsize) for _ in range(4)) for _ in range(n)]
            ]),
            False
        )
    ]


channel_settle_test_values_random = channel_settle_test_values_random(100)
