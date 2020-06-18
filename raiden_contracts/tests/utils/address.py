import random

from raiden_contracts.tests.utils.constants import UINT256_MAX
from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.type_aliases import PrivateKey


def get_random_privkey() -> PrivateKey:
    """Returns a random private key"""
    return PrivateKey(random.randint(1, UINT256_MAX).to_bytes(32, byteorder="big"))


def get_random_address() -> str:
    """Returns a random valid ethereum address"""
    return private_key_to_address(get_random_privkey())
