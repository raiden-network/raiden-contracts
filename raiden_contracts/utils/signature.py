from typing import Union

from coincurve import PrivateKey, PublicKey
from eth_utils import keccak, remove_0x_prefix, to_bytes, to_checksum_address

from .type_aliases import Address

sha3 = keccak


def sign(privkey: str, msg: bytes, v=0) -> bytes:
    assert isinstance(msg, bytes)
    assert isinstance(privkey, str)

    pk = PrivateKey.from_hex(remove_0x_prefix(privkey))
    assert len(msg) == 32

    sig = pk.sign_recoverable(msg, hasher=None)
    assert len(sig) == 65

    sig = sig[:-1] + bytes([sig[-1] + v])

    return sig


def private_key_to_address(private_key: Union[str, bytes]) -> Address:
    """ Converts a private key to an Ethereum address. """
    if isinstance(private_key, str):
        private_key_bytes = to_bytes(hexstr=private_key)
    else:
        private_key_bytes = private_key
    pk = PrivateKey(private_key_bytes)
    return public_key_to_address(pk.public_key)


def public_key_to_address(public_key: Union[PublicKey, bytes]) -> Address:
    """ Converts a public key to an Ethereum address. """
    if isinstance(public_key, PublicKey):
        public_key = public_key.format(compressed=False)
    assert isinstance(public_key, bytes)
    return to_checksum_address(sha3(public_key[1:])[-20:])
