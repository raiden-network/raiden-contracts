raiden_contracts_version = '0.3.0'
MAX_UINT256 = 2 ** 256 - 1
MAX_UINT192 = 2 ** 192 - 1
MAX_UINT32 = 2 ** 32 - 1
fake_address = '0x03432'
empty_address = '0x0000000000000000000000000000000000000000'
passphrase = '0'


def fake_hex(size, fill='00'):
    return '0x' + ''.join([fill for i in range(0, size)])


def fake_bytes(size, fill='00'):
    return bytearray.fromhex(fake_hex(size, fill)[2:])
