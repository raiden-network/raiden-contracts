from enum import IntEnum

from eth_utils.units import units

from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.type_aliases import Address

MAX_UINT256 = 2 ** 256 - 1
MAX_UINT192 = 2 ** 192 - 1
MAX_UINT32 = 2 ** 32 - 1
FAKE_ADDRESS = "0x03432"
EMPTY_ADDRESS = Address("0x0000000000000000000000000000000000000000")
EMPTY_BALANCE_HASH = b"\x00" * 32
EMPTY_ADDITIONAL_HASH = b"\x00" * 32
EMPTY_LOCKSROOT = b"\x00" * 32
EMPTY_SIGNATURE = b"\x00" * 65
passphrase = "0"
FAUCET_PRIVATE_KEY = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
FAUCET_ADDRESS = private_key_to_address(FAUCET_PRIVATE_KEY)
FAUCET_ALLOWANCE = 100 * int(units["ether"])
CONTRACT_DEPLOYER_ADDRESS = FAUCET_ADDRESS


class TestLockIndex(IntEnum):
    EXPIRATION = 0
    AMOUNT = 1
    SECRETHASH = 2
    SECRET = 3
