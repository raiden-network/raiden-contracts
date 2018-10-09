from enum import IntEnum


MAX_UINT256 = 2 ** 256 - 1
MAX_UINT192 = 2 ** 192 - 1
MAX_UINT32 = 2 ** 32 - 1
FAKE_ADDRESS = '0x03432'
EMPTY_ADDRESS = '0x0000000000000000000000000000000000000000'
EMPTY_BALANCE_HASH = b'\x00' * 32
EMPTY_ADDITIONAL_HASH = b'\x00' * 32
EMPTY_LOCKSROOT = b'\x00' * 32
EMPTY_SIGNATURE = b'\x00' * 65
passphrase = '0'


class TestLockIndex(IntEnum):
    EXPIRATION = 0
    AMOUNT = 1
    SECRETHASH = 2
    SECRET = 3


def fake_hex(size, fill='00'):
    return '0x' + ''.join([fill for i in range(0, size)])


def fake_bytes(size, fill='00'):
    return bytes.fromhex(fake_hex(size, fill)[2:])
