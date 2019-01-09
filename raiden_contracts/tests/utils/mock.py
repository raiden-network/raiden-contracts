import string
from random import choice


def fake_hex(size, fill='00'):
    return '0x' + ''.join([fill for i in range(0, size)])


def fake_bytes(size, fill='00'):
    return bytes.fromhex(fake_hex(size, fill)[2:])


def make_address():
    return bytes(''.join(choice(string.printable) for _ in range(20)), encoding='utf-8')
