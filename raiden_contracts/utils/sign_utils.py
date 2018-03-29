from coincurve import PrivateKey
from eth_utils import remove_0x_prefix


def sign(privkey: str, msg: bytes, v=0) -> bytes:
    if isinstance(privkey, bytes):
        privkey = hex(int.from_bytes(privkey, byteorder='big'))
    assert isinstance(msg, bytes)
    assert isinstance(privkey, str)

    pk = PrivateKey.from_hex(remove_0x_prefix(privkey))
    assert len(msg) == 32

    sig = pk.sign_recoverable(msg, hasher=None)
    assert len(sig) == 65

    sig = sig[:-1] + bytes([sig[-1] + v])

    return sig
