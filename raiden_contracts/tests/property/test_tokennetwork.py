# -*- coding: utf-8 -*-
import contextlib

import eth_tester.backends.pyevm.main as pyevm_main

from coincurve import PrivateKey
from eth_utils import (
    encode_hex,
    to_canonical_address,
    to_checksum_address,
)
from eth_tester.exceptions import TransactionFailed
from hypothesis import assume
from hypothesis.stateful import GenericStateMachine
from hypothesis.strategies import (
    integers,
    just,
    one_of,
    sampled_from,
    tuples,
)
from raiden_libs.test.fixtures.web3 import ethereum_tester
from raiden_libs.utils import private_key_to_address
from raiden_contracts.constants import (
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.tests.utils import (
    deploy_contract,
    deploy_custom_token,
    get_web3,
    get_token_network,
    make_address,
)
from raiden_contracts.tests.property.strategies import direct_transfer
from web3 import Web3
from web3.exceptions import ValidationError

DEPOSIT = 'deposit'
CLOSE = 'close'
UPDATE_TRANSFER = 'updateTransfer'
MINE = 'mine'
EMPTY_MERKLE_ROOT = b'\x00' * 32
GAS_LIMIT = 5942246


@contextlib.contextmanager
def transaction_must_fail(error_message):
    try:
        yield
    except TransactionFailed:
        pass
    else:
        raise ValueError(error_message)


class BlockGasLimitReached(ValidationError):
    pass


class TokenNetworkStateMachine(GenericStateMachine):
    """ Generates random operations (e.g. deposit, close, updateTransfer) to
    test against a netting channel.
    """

    def __init__(self):
        super().__init__()

        self.log = list()
        self.settle_timeout = 10

        deployer_key = PrivateKey(secret=b'deploy_key')

        pyevm_main.GENESIS_GAS_LIMIT = 6 * 10 ** 6
        self.tester_chain = ethereum_tester()

        self.web3 = get_web3(self.tester_chain, deployer_key)

        self.tokens = [
            deploy_custom_token(
                self.web3,
                deployer_key,
            ),
            deploy_custom_token(
                self.web3,
                deployer_key,
            ),
        ]
        self.token = self.tokens[0]

        self.token_addresses = [
            token.address
            for token in self.tokens
        ]

        self.private_keys = [
            PrivateKey(secret=b'p1'),
            PrivateKey(secret=b'p2'),
            PrivateKey(secret=b'p3'),
        ]

        # Create and fund accounts with Ether and CustomToken
        self.addresses = []
        token_amount = 100000
        for private_key in self.private_keys:
            self.tester_chain.add_account(private_key.to_hex())

            address = private_key_to_address(private_key.to_hex())
            self.tester_chain.send_transaction({
                'from': self.tester_chain.get_accounts()[0],
                'to': address,
                'gas': 21000,
                'value': self.web3.toWei(100, 'ether'),
            })

            self.token.functions.transfer(
                address,
                token_amount,
            ).transact({
                'from': private_key_to_address(deployer_key.to_hex()),
            })

            self.addresses.append(address)

        self.secret_registry = deploy_contract(
            self.web3,
            CONTRACT_SECRET_REGISTRY,
            deployer_key,
            [],  # No Libs
            [],  # No Args
        )

        self.token_network_registry = deploy_contract(
            self.web3,
            CONTRACT_TOKEN_NETWORK_REGISTRY,
            deployer_key,
            [],
            [
                self.secret_registry.address,
                1,
                TEST_SETTLE_TIMEOUT_MIN,
                TEST_SETTLE_TIMEOUT_MAX,
            ],
        )

        self.token_network_registry.functions.createERC20TokenNetwork(
            self.token.address,
        ).transact()

        token_network_address = self.token_network_registry.functions.token_to_token_networks(
            self.token.address,
        ).call()

        self.token_network = get_token_network(
            self.web3,
            to_checksum_address(token_network_address),
        )

        channel_identifier = self.open_channel()

        self.closing_address = None
        self.update_transfer_called = False

        self.participant_addresses = {
            self.addresses[0],
            self.addresses[1],
        }

        self.channel_addresses = [
            channel_identifier,
            make_address(),
        ]

    def steps(self):
        transfer = direct_transfer(  # pylint: disable=no-value-for-parameter
            just(self.token_network.address),
            sampled_from(self.token_addresses),
            sampled_from(self.channel_addresses),
            sampled_from(self.addresses),
            just(EMPTY_MERKLE_ROOT),
        )

        deposit_op = tuples(
            just(DEPOSIT),
            integers(min_value=1),
            sampled_from(self.private_keys),
            sampled_from(self.private_keys),
        )

        close_op = tuples(
            just(CLOSE),
            transfer,
            sampled_from(self.private_keys),
            sampled_from(self.private_keys),
        )

        update_transfer_op = tuples(
            just(UPDATE_TRANSFER),
            transfer,
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
                self.contract_close(step[1], step[2], step[3])
            except BlockGasLimitReached:
                assume(False)

        elif op == UPDATE_TRANSFER:
            try:
                self.contract_update_transfer(step[1], step[2], step[3])
            except BlockGasLimitReached:
                assume(False)

        elif op == MINE:
            self.tester_chain.mine_blocks(num_blocks=step[1])

    def is_participant(self, address):
        return address in self.participant_addresses

    def contract_deposit(self, deposit_amount, sender_pkey, partner_pkey):
        sender_address = private_key_to_address(sender_pkey.to_hex())
        partner_address = private_key_to_address(partner_pkey.to_hex())

        token_balance = self.token.functions.balanceOf(
            sender_address,
        ).call()

        # Sampling private keys could choose the pair
        # from the same item.
        # skip as getChannelInfo fails for the sender==receiver
        if sender_address == partner_address:
            return

        (channel_identifier, _, channel_state) = self.token_network.functions.getChannelInfo(
            participant1=sender_address,
            participant2=partner_address,
        ).call()

        (existing_deposit, _, _, _, _) = self.token_network.functions.getChannelParticipantInfo(
            participant=sender_address,
            partner=partner_address,
        ).call()

        deposit_amount += existing_deposit

        if not self.is_participant(sender_address):
            with transaction_must_fail('deposit from non-participant didnt fail'):
                self.token_network.functions.setTotalDeposit(
                    sender_address,
                    deposit_amount,
                    partner_address,
                ).transact({
                    'from': sender_address,
                })

        elif channel_state != 1:
            with transaction_must_fail('deposit with closed channel didnt fail'):
                self.token_network.functions.setTotalDeposit(
                    sender_address,
                    deposit_amount,
                    partner_address,
                ).transact({
                    'from': sender_address,
                })

        elif token_balance < deposit_amount:
            with transaction_must_fail('having insufficient funds for a deposit didnt fail'):
                self.token_network.functions.setTotalDeposit(
                    sender_address,
                    deposit_amount,
                    partner_address,
                ).transact({
                    'from': sender_address,
                })

        else:
            self.token.functions.approve(
                self.token_network.address,
                deposit_amount,
            ).transact({
                'from': sender_address,
            })

            self.token_network.functions.setTotalDeposit(
                sender_address,
                deposit_amount,
                partner_address,
            ).transact({
                'from': sender_address,
            })

    def contract_close(self, transfer, closer_pkey, partner_pkey):
        closer_signature = transfer.sign(
            closer_pkey,
            private_key_to_address(closer_pkey.to_hex()),
        )

        closer_address = private_key_to_address(closer_pkey.to_hex())
        partner_address = private_key_to_address(partner_pkey.to_hex())
        transfer_data = transfer.to_bytes()

        transfer_hash = Web3.sha3(
            hexstr=encode_hex(transfer_data[:-65]),
        )

        if closer_address == partner_address:
            return

        (_, _, channel_state) = self.token_network.functions.getChannelInfo(
            participant1=closer_address,
            participant2=partner_address,
        ).call()

        if not self.is_participant(transfer.sender):
            msg = 'close with transfer data from a non participant didnt fail'
            with transaction_must_fail(msg):
                self.token_network.functions.closeChannel(
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    closer_signature,
                ).transact()

        elif transfer.sender == closer_address:
            with transaction_must_fail('close with self signed transfer didnt fail'):
                self.token_network.functions.closeChannel(
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    closer_signature,
                ).transact()

        elif channel_state == 2:
            with transaction_must_fail('close called twice didnt fail'):
                self.token_network.functions.closeChannel(
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    closer_signature,
                ).transact()

        elif not self.is_participant(closer_address):
            with transaction_must_fail('close called by a non participant didnt fail'):
                self.token_network.functions.closeChannel(
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    closer_signature,
                ).transact()

        elif transfer.channel != to_canonical_address(self.token_network.address):
            msg = 'close called with a transfer for a different channe didnt fail'
            with transaction_must_fail(msg):
                self.token_network.functions.closeChannel(
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    closer_signature,
                ).transact()

        else:
            self.token_network.functions.closeChannel(
                partner_address,
                transfer.balance_hash(),
                transfer.nonce,
                transfer_hash,
                closer_signature,
            ).transact()

            self.closing_address = closer_address

    def contract_update_transfer(self, transfer, sender_pkey, partner_pkey):
        sender_signature = transfer.sign(
            sender_pkey,
            private_key_to_address(sender_pkey.to_hex()),
        )

        receiver_signature = transfer.sign(
            partner_pkey,
            private_key_to_address(partner_pkey.to_hex()),
        )

        sender_address = private_key_to_address(sender_pkey.to_hex())
        partner_address = private_key_to_address(partner_pkey.to_hex())

        transfer_data = transfer.to_bytes()
        transfer_hash = Web3.sha3(
            hexstr=encode_hex(transfer_data[:-65]),
        )

        # Sampling private keys could choose the pair
        # from the same item.
        # skip as getChannelInfo fails for the sender==receiver
        if sender_address == partner_address:
            return

        (_, settle_block_number, channel_state) = self.token_network.functions.getChannelInfo(
            sender_address,
            partner_address,
        ).call({
            'from': self.web3.eth.accounts[0],
            'gas': GAS_LIMIT,
        })

        is_closed = channel_state == 2
        block_number = self.tester_chain.get_block_by_number('latest')['number']
        is_settlement_period_over = is_closed and settle_block_number < block_number

        if not self.is_participant(transfer.sender):
            msg = 'updateTransfer with transfer data from a non participant didnt fail'
            with transaction_must_fail(msg):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        elif transfer.sender == sender_address:
            with transaction_must_fail('updateTransfer with self signed transfer didnt fail'):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        elif self.update_transfer_called:
            with transaction_must_fail('updateTransfer called twice didnt fail'):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        elif not self.is_participant(sender_address):
            with transaction_must_fail('updateTransfer called by a non participant didnt fail'):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        elif transfer.channel != self.channel_addresses[0]:
            msg = 'updateTransfer called with a transfer for a different channel didnt fail'
            with transaction_must_fail(msg):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        elif not is_closed:
            with transaction_must_fail('updateTransfer called on an open channel and didnt fail'):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        elif is_settlement_period_over:
            msg = 'updateTransfer called after end of the settlement period and didnt fail'
            with transaction_must_fail(msg):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        elif sender_address == self.closing_address:
            with transaction_must_fail('updateTransfer called by the closer and it didnt fail'):
                self.token_network.functions.updateNonClosingBalanceProof(
                    sender_address,
                    partner_address,
                    transfer.balance_hash(),
                    transfer.nonce,
                    transfer_hash,
                    sender_signature,
                    receiver_signature,
                ).transact()

        else:
            self.token_network.functions.updateNonClosingBalanceProof(
                sender_address,
                partner_address,
                transfer.balance_hash(),
                transfer.nonce,
                transfer_hash,
                sender_signature,
                receiver_signature,
            ).transact()
            self.update_transfer_called = True

    def open_channel(self):
        tx_hash = self.token_network.functions.openChannel(
            self.addresses[0],
            self.addresses[1],
            TEST_SETTLE_TIMEOUT_MAX,
        ).transact({
            'from': self.web3.eth.accounts[0],
            'gas': GAS_LIMIT,
        })

        tx_receipt = self.web3.eth.getTransactionReceipt(tx_hash)
        tx_logs = self.token_network.events.ChannelOpened().processReceipt(
            tx_receipt,
        )

        return tx_logs[0]['args']['channel_identifier']


# FIXME: Disable the test for now. A more formalized sampling
# of data should be done in the following issue:
# https://github.com/raiden-network/raiden-contracts/issues/108
# TokenNetworkTestCase = TokenNetworkStateMachine.TestCase
