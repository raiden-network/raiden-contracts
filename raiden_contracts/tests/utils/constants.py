from enum import IntEnum
from typing import NamedTuple

from eth_utils.units import units

from raiden_contracts.utils.signature import private_key_to_address

UINT256_MAX = 2 ** 256 - 1
NOT_ADDRESS = "0xaaa"
FAKE_ADDRESS = "0x00112233445566778899aabbccddeeff00112233"
EMPTY_BALANCE_HASH = b"\x00" * 32
EMPTY_ADDITIONAL_HASH = b"\x00" * 32
EMPTY_SIGNATURE = b"\x00" * 65
passphrase = "0"
FAUCET_PRIVATE_KEY = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
FAUCET_ADDRESS = private_key_to_address(FAUCET_PRIVATE_KEY)
FAUCET_ALLOWANCE = 100 * int(units["ether"])
CONTRACT_DEPLOYER_ADDRESS = FAUCET_ADDRESS
NONEXISTENT_LOCKSROOT = b"\x00" * 32
SECONDS_PER_DAY = 60 * 60 * 24

# Constants for ServiceRegistry testing
SERVICE_DEPOSIT = 5000 * (10 ** 18)
DEFAULT_BUMP_NUMERATOR = 6
DEFAULT_BUMP_DENOMINATOR = 5
DEFAULT_DECAY_CONSTANT = 200 * SECONDS_PER_DAY
DEFAULT_REGISTRATION_DURATION = 180 * SECONDS_PER_DAY
DEFAULT_MIN_PRICE = 1000


class TestLockIndex(IntEnum):
    EXPIRATION = 0
    AMOUNT = 1
    SECRETHASH = 2
    SECRET = 3


class OnchainBalanceProof(NamedTuple):
    balance_hash: bytes
    nonce: int
    additional_hash: bytes
    original_signature: bytes
