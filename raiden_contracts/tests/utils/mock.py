import random
import string
from os import urandom
from web3 import Web3


def fake_hex(size, fill='00'):
    return '0x' + ''.join([fill for i in range(0, size)])


def fake_bytes(size, fill='00'):
    return bytes.fromhex(fake_hex(size, fill)[2:])


def make_address():
    return bytes(''.join(random.choice(string.printable) for _ in range(20)), encoding='utf-8')


def random_secret():
    secret = urandom(32)
    return (Web3.soliditySha3(['bytes32'], [secret]), secret)


def get_random_values_for_sum(values_sum):
    amount = 0
    values = []
    while amount < values_sum:
        value = randint(1, values_sum - amount)
        values.append(value)
        amount += value
    return values
