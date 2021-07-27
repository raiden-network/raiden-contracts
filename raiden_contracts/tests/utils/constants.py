from enum import IntEnum
from typing import NamedTuple

from eth_typing import HexAddress, HexStr
from eth_utils import decode_hex
from eth_utils.units import units

from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.type_aliases import (
    AdditionalHash,
    BalanceHash,
    Locksroot,
    PrivateKey,
    Signature,
)

UINT256_MAX = 2 ** 256 - 1
NOT_ADDRESS = "0xaaa"
FAKE_ADDRESS = HexAddress(HexStr("0x00112233445566778899aabbccddeeff00112233"))
EMPTY_HEXADDRESS = "0x0000000000000000000000000000000000000000"
EMPTY_BALANCE_HASH = BalanceHash(b"\x00" * 32)
EMPTY_ADDITIONAL_HASH = AdditionalHash(b"\x00" * 32)
EMPTY_LOCKSROOT = Locksroot(b"\x00" * 32)
EMPTY_SIGNATURE = Signature(b"\x00" * 65)
passphrase = "0"
FAUCET_PRIVATE_KEY = PrivateKey(
    decode_hex("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
)
FAUCET_ADDRESS = private_key_to_address(FAUCET_PRIVATE_KEY)
FAUCET_ALLOWANCE = 100 * int(units["ether"])
DEPLOYER_ADDRESS = FAUCET_ADDRESS
NONEXISTENT_LOCKSROOT = b"\x00" * 32
SECONDS_PER_DAY = 60 * 60 * 24

# Constants for ServiceRegistry testing
SERVICE_DEPOSIT = 5000 * (10 ** 18)
DEFAULT_BUMP_NUMERATOR = 6
DEFAULT_BUMP_DENOMINATOR = 5
DEFAULT_DECAY_CONSTANT = 200 * SECONDS_PER_DAY
DEFAULT_REGISTRATION_DURATION = 180 * SECONDS_PER_DAY
DEFAULT_MIN_PRICE = 1000


class LockIndex(IntEnum):
    EXPIRATION = 0
    AMOUNT = 1
    SECRETHASH = 2
    SECRET = 3


class OnchainBalanceProof(NamedTuple):
    balance_hash: bytes
    nonce: int
    additional_hash: bytes
    original_signature: bytes
