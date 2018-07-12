from eth_utils import keccak
from hypothesis.strategies import (
    binary,
    composite,
    integers,
)


UINT64_MAX = 2 ** 64 - 1
UINT256_MAX = 2 ** 256 - 1

privatekeys = binary(min_size=32, max_size=32)
identifier = integers(min_value=0, max_value=UINT64_MAX)
nonce = integers(min_value=1, max_value=UINT64_MAX)
transferred_amount = integers(min_value=0, max_value=UINT256_MAX)


class Transfer:
    cmdid = 5  # DirectTransfer

    def __init__(
            self,
            message_identifier,
            payment_identifier,
            nonce,
            registry_address,
            token,
            channel,
            transferred_amount,
            locked_amount,
            recipient,
            locksroot,
    ):
        self.message_identifier = message_identifier
        self.payment_identifier = payment_identifier
        self.nonce = nonce
        self.registry_address = registry_address
        self.token = token
        self.channel = channel
        self.transferred_amount = transferred_amount
        self.locked_amount = locked_amount
        self.recipient = recipient
        self.locksroot = locksroot

    def sign(self, private_key, node_address):
        """ Sign message using `private_key`. """
        signature = private_key.sign_recoverable(
            self.to_bytes(),
            hasher=keccak,
        )
        if len(signature) != 65:
            raise ValueError('invalid signature')

        signature = signature[:-1] + chr(signature[-1] + 27).encode()

        self.signature = signature

        self.sender = node_address
        self.signature = signature

        return signature

    def to_bytes(self):
        arr = bytearray()
        arr.extend(self.message_identifier.to_bytes(8, byteorder='big'))
        arr.extend(self.payment_identifier.to_bytes(8, byteorder='big'))
        arr.extend(self.nonce.to_bytes(8, byteorder='big'))
        arr.extend(self.token.encode())
        arr.extend(self.registry_address.encode())
        arr.extend(self.channel)
        arr.extend(self.transferred_amount.to_bytes(32, byteorder='big'))
        arr.extend(self.locked_amount.to_bytes(32, byteorder='big'))
        arr.extend(self.recipient.encode())
        arr.extend(self.locksroot)
        return arr

    def balance_hash(self):
        # balance_hash Hash of (transferred_amount, locked_amount, locksroot).
        return keccak(text='{0}{1}{2}'.format(
            self.transferred_amount,
            self.locked_amount,
            self.locksroot,
        ))


@composite
def direct_transfer(draw, registry_address, token, channel, recipient, locksroot):
    return Transfer(
        draw(identifier),
        draw(identifier),
        draw(nonce),
        draw(registry_address),
        draw(token),
        draw(channel),
        draw(transferred_amount),
        0,
        draw(recipient),
        draw(locksroot),
    )
