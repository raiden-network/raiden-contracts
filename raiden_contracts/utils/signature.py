from typing import Union

from coincurve import PrivateKey, PublicKey
from eth_typing import HexStr
from eth_utils import keccak, remove_0x_prefix, to_bytes, to_checksum_address
from eth_utils.typing import ChecksumAddress

sha3 = keccak


def sign(privkey: str, msg_hash: bytes, v: int = 0) -> bytes:
    if not isinstance(msg_hash, bytes):
        raise TypeError("sign(): msg_hash is not an instance of bytes")
    if len(msg_hash) != 32:
        raise ValueError("sign(): msg_hash has to be exactly 32 bytes")
    if not isinstance(privkey, str):
        raise TypeError("sign(): privkey is not an instance of str")
    if v not in {0, 27}:
        raise ValueError(f"sign(): got v = {v} expected 0 or 27.")

    pk = PrivateKey.from_hex(remove_0x_prefix(HexStr(privkey)))
    sig: bytes = pk.sign_recoverable(msg_hash, hasher=None)
    assert len(sig) == 65

    pub = pk.public_key
    recovered = PublicKey.from_signature_and_message(sig, msg_hash, hasher=None)
    assert pub == recovered

    sig = sig[:-1] + bytes([sig[-1] + v])

    return sig


def private_key_to_address(private_key: Union[str, bytes]) -> ChecksumAddress:
    """ Converts a private key to an Ethereum address. """
    if isinstance(private_key, str):
        private_key_bytes = to_bytes(hexstr=private_key)
    else:
        private_key_bytes = private_key
    pk = PrivateKey(private_key_bytes)
    return public_key_to_address(pk.public_key)


def public_key_to_address(public_key: Union[PublicKey, bytes]) -> ChecksumAddress:
    """ Converts a public key to an Ethereum address. """
    if isinstance(public_key, PublicKey):
        public_key = public_key.format(compressed=False)
    assert isinstance(public_key, bytes)
    return to_checksum_address(sha3(public_key[1:])[-20:])
