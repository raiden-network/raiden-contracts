# -*- coding: utf-8 -*-
import contextlib

from coincurve import PrivateKey
from eth_utils import (
    encode_hex,
    keccak,
    to_canonical_address,
)
from hypothesis import assume
from hypothesis.stateful import GenericStateMachine
from hypothesis.strategies import (
    binary,
    composite,
    integers,
    just,
    one_of,
    sampled_from,
    tuples,
)
from raiden_libs.test.fixtures.web3 import ethereum_tester
from raiden_libs.utils import private_key_to_address
from web3 import Web3

from raiden_contracts.constants import (
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.tests.utils.contracts import (
    deploy_contract,
    deploy_custom_token,
    get_web3,
)

UINT64_MAX = 2 ** 64 - 1
UINT256_MAX = 2 ** 256 - 1
DEPOSIT = 'deposit'
CLOSE = 'close'
UPDATE_TRANSFER = 'updateTransfer'
MINE = 'mine'
EMPTY_MERKLE_ROOT = b'\x00' * 32

privatekeys = binary(min_size=32, max_size=32)
identifier = integers(min_value=0, max_value=UINT64_MAX)
nonce = integers(min_value=1, max_value=UINT64_MAX)
transferred_amount = integers(min_value=0, max_value=UINT256_MAX)


@contextlib.contextmanager
def transaction_must_fail(error_message):
    try:
        yield
    except Exception:  # TransactionFailed:
        pass
    else:
        raise ValueError(error_message)


class BlockGasLimitReached(BaseException):
    pass


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


class NettingChannelStateMachine(GenericStateMachine):
    """ Generates random operations (e.g. deposit, close, updateTransfer) to
    test against a netting channel.
    """

    def __init__(self):
        super().__init__()

        deployer_key = Web3.sha3(b'deploy_key')

        self.tester_chain = ethereum_tester()
        web3 = get_web3(self.tester_chain, deployer_key)

        self.private_keys = [
            PrivateKey(secret=b'p1'),
            PrivateKey(secret=b'p2'),
            PrivateKey(secret=b'p3'),
        ]
        self.addresses = [
            private_key_to_address(private_key.to_hex())
            for private_key in self.private_keys
        ]
        self.log = list()
        self.settle_timeout = 10
        self.token_amount = 1000

        self.tokens = [
            deploy_custom_token(
                web3,
                deployer_key,
            ),
            deploy_custom_token(
                web3,
                deployer_key,
            ),
        ]
        self.token = self.tokens[0]

        self.token_addresses = [
            token.address
            for token in self.tokens
        ]

        self.secret_registry = deploy_contract(
            web3,
            CONTRACT_SECRET_REGISTRY,
            deployer_key,
            [],  # No Libs
            [],  # No Args
        )

        self.token_network = deploy_contract(
            web3,
            CONTRACT_TOKEN_NETWORK,
            deployer_key,
            [],
            [
                self.token.address,
                self.secret_registry.address,
                1,
                TEST_SETTLE_TIMEOUT_MIN,
                TEST_SETTLE_TIMEOUT_MAX,
            ],
        )

        channel_identifier = self.token_network.functions.openChannel(
            participant1=self.addresses[0],
            participant2=self.addresses[1],
            settle_timeout=TEST_SETTLE_TIMEOUT_MAX,
        ).transact()

        self.closing_address = None
        self.update_transfer_called = False

        self.participant_addresses = {
            self.addresses[0],
            self.addresses[1],
        }

        self.channel_addresses = [
            channel_identifier,
            # make_address(),  # used to test invalid transfers
        ]

    def steps(self):
        transfer = direct_transfer(  # pylint: disable=no-value-for-parameter
            sampled_from(self.token_network.address),
            sampled_from(self.token_addresses),
            sampled_from(self.channel_addresses),
            sampled_from(self.addresses),
            just(EMPTY_MERKLE_ROOT),
        )

        deposit_op = tuples(
            just(DEPOSIT),
            integers(min_value=0),
            sampled_from(self.private_keys),
            sampled_from(self.private_keys),
        )

        close_op = tuples(
            just(CLOSE),
            transfer,
            sampled_from(self.private_keys),
            sampled_from(self.private_keys),
            sampled_from(self.private_keys),
        )

        update_transfer_op = tuples(
            just(UPDATE_TRANSFER),
            transfer,
            sampled_from(self.private_keys),
            sampled_from(self.private_keys),
            sampled_from(self.private_keys),
        )

        transaction_ops = one_of(
            deposit_op,
            close_op,
            update_transfer_op,
        )

        mine_op = tuples(
            just(MINE),
            integers(min_value=1, max_value=self.settle_timeout * 5),
        )

        # increases likely hood of the mine op, while permitting transactions
        # to run in the same block
        return one_of(
            transaction_ops,
            mine_op,
        )

    def execute_step(self, step):
        op = step[0]

        if op == DEPOSIT:
            try:
                self.contract_deposit(step[1], step[2], step[3])
            except BlockGasLimitReached:
                assume(False)

        elif op == CLOSE:
            try:
                self.contract_close(step[1], step[2], step[3], step[4])
            except BlockGasLimitReached:
                assume(False)

        elif op == UPDATE_TRANSFER:
            try:
                self.contract_update_transfer(step[1], step[2], step[3], step[4])
            except BlockGasLimitReached:
                assume(False)

        elif op == MINE:
            self.tester_chain.mine_blocks(num_blocks=step[1])

    def is_participant(self, address):
        return address in self.participant_addresses

    def contract_deposit(self, deposit_amount, sender_pkey, receiver_pkey):
        sender_address = private_key_to_address(sender_pkey.to_hex())
        receiver_address = private_key_to_address(receiver_pkey.to_hex())
        token_balance = self.token.functions.balanceOf(
            sender_address,
        ).transact()

        channelInfo = self.token_network.functions.getChannelInfo(
            sender_address,
            receiver_address,
        ).transact()

        if not self.is_participant(sender_address):
            with transaction_must_fail('deposit from non-participant didnt fail'):
                self.netting_channel.deposit(
                    deposit_amount,
                    sender=sender_pkey,
                )

        elif channelInfo[2] != 0:
            with transaction_must_fail('deposit with closed channel didnt fail'):
                self.netting_channel.deposit(
                    deposit_amount,
                    sender=sender_pkey,
                )

        elif token_balance < deposit_amount:
            with transaction_must_fail('having insufficient funds for a deposit didnt fail'):
                self.netting_channel.deposit(
                    deposit_amount,
                    sender=sender_pkey,
                )

        else:
            self.netting_channel.deposit(
                deposit_amount,
                sender=sender_pkey,
            )

    def contract_close(self, transfer, signing_pkey, sender_pkey, receiver_pkey):
        transfer.sign(
            signing_pkey,
            private_key_to_address(signing_pkey.to_hex()),
        )

        sender_address = private_key_to_address(sender_pkey.to_hex())
        receiver_address = private_key_to_address(receiver_pkey.to_hex())
        transfer_data = transfer.to_bytes()

        transfer_hash = Web3.sha3(
            hexstr=encode_hex(transfer_data[:-65]),
        )

        channelInfo = self.token_network.functions.getChannelInfo(
            sender_address,
            receiver_address,
        ).transact()

        if not self.is_participant(transfer.sender):
            msg = 'close with transfer data from a non participant didnt fail'
            with transaction_must_fail(msg):
                self.netting_channel.close(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif transfer.sender == sender_address:
            with transaction_must_fail('close with self signed transfer didnt fail'):
                self.netting_channel.close(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif channelInfo[2] != 0:  # pylint: disable=no-member
            with transaction_must_fail('close called twice didnt fail'):
                self.netting_channel.close(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif not self.is_participant(sender_address):
            with transaction_must_fail('close called by a non participant didnt fail'):
                self.netting_channel.close(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif transfer.channel != to_canonical_address(self.netting_channel.address):
            msg = 'close called with a transfer for a different channe didnt fail'
            with transaction_must_fail(msg):
                self.netting_channel.close(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        else:
            self.netting_channel.close(  # pylint: disable=no-member
                transfer.nonce,
                transfer.transferred_amount,
                transfer.locksroot,
                transfer_hash,
                transfer.signature,
                sender=sender_pkey,
            )

            self.closing_address = sender_address

    def contract_update_transfer(self, transfer, signing_pkey, sender_pkey, receiver_pkey):
        transfer.sign(
            signing_pkey,
            private_key_to_address(signing_pkey.to_hex()),
        )

        sender_address = private_key_to_address(sender_pkey.to_hex())
        receiver_address = private_key_to_address(receiver_pkey.to_hex())

        transfer_data = transfer.to_bytes()
        transfer_hash = Web3.sha3(
            hexstr=encode_hex(transfer_data[:-65]),
        )

        channelInfo = self.token_network.functions.getChannelInfo(
            sender_address,
            receiver_address,
        ).transact()
        settlement_end = channelInfo[1]

        is_closed = channelInfo[2] == 2
        is_settlement_period_over = is_closed and settlement_end < self.tester_chain.block.number

        if not self.is_participant(transfer.sender):
            msg = 'updateTransfer with transfer data from a non participant didnt fail'
            with transaction_must_fail(msg):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif transfer.sender == sender_address:
            with transaction_must_fail('updateTransfer with self signed transfer didnt fail'):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif self.update_transfer_called:
            with transaction_must_fail('updateTransfer called twice didnt fail'):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif not self.is_participant(sender_address):
            with transaction_must_fail('updateTransfer called by a non participant didnt fail'):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif transfer.channel != self.channel_addresses[0]:
            msg = 'updateTransfer called with a transfer for a different channel didnt fail'
            with transaction_must_fail(msg):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif not is_closed:
            with transaction_must_fail('updateTransfer called on an open channel and didnt fail'):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif is_settlement_period_over:
            msg = 'updateTransfer called after end of the settlement period and didnt fail'
            with transaction_must_fail(msg):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        elif sender_address == self.closing_address:
            with transaction_must_fail('updateTransfer called by the closer and it didnt fail'):
                self.netting_channel.updateTransfer(  # pylint: disable=no-member
                    transfer.nonce,
                    transfer.transferred_amount,
                    transfer.locksroot,
                    transfer_hash,
                    transfer.signature,
                    sender=sender_pkey,
                )

        else:
            self.netting_channel.updateTransfer(  # pylint: disable=no-member
                transfer.nonce,
                transfer.transferred_amount,
                transfer.locksroot,
                transfer_hash,
                transfer.signature,
                sender=sender_pkey,
            )
            self.update_transfer_called = True


NettingChannelTestCase = NettingChannelStateMachine.TestCase
