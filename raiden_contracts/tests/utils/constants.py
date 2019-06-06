from enum import IntEnum

from eth_typing.evm import HexAddress
from eth_utils import keccak
from eth_utils.units import units

from raiden_contracts.utils.signature import private_key_to_address

UINT256_MAX = 2 ** 256 - 1
FAKE_ADDRESS = "0x03432"
EMPTY_ADDRESS = HexAddress("0x0000000000000000000000000000000000000000")
EMPTY_BALANCE_HASH = b"\x00" * 32
EMPTY_ADDITIONAL_HASH = b"\x00" * 32
LOCKSROOT_OF_NO_LOCKS = keccak(b"")
EMPTY_SIGNATURE = b"\x00" * 65
passphrase = "0"
FAUCET_PRIVATE_KEY = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
FAUCET_ADDRESS = private_key_to_address(FAUCET_PRIVATE_KEY)
FAUCET_ALLOWANCE = 100 * int(units["ether"])
CONTRACT_DEPLOYER_ADDRESS = FAUCET_ADDRESS
NONEXISTENT_LOCKSROOT = b"\x00" * 32


class TestLockIndex(IntEnum):
    EXPIRATION = 0
    AMOUNT = 1
    SECRETHASH = 2
    SECRET = 3
