import string
from random import choice


def fake_hex(size: int, fill: str = "00") -> str:
    return "0x" + "".join([fill for i in range(0, size)])


def fake_bytes(size: int, fill: str = "00") -> bytes:
    return bytes.fromhex(fake_hex(size, fill)[2:])


def make_address() -> bytes:
    return bytes("".join(choice(string.printable) for _ in range(20)), encoding="utf-8")
