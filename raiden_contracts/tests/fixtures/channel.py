import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK, SETTLE_TIMEOUT_MIN
from raiden_contracts.utils.sign import sign_balance_proof, hash_balance_data
from .token_network import *  # flake8: noqa
from .secret_registry import *  # flake8: noqa


@pytest.fixture()
def create_channel(token_network):
    def get(A, B, settle_timeout=SETTLE_TIMEOUT_MIN):
        token_network.transact().openChannel(A, B, settle_timeout)
        channel_identifier = token_network.call().last_channel_index()
        assert token_network.call().getChannelInfo(channel_identifier)[0] == settle_timeout
        assert token_network.call().getChannelParticipantInfo(channel_identifier, A)[1] is True
        assert token_network.call().getChannelParticipantInfo(channel_identifier, B)[1] is True
        return channel_identifier
    return get


@pytest.fixture()
def channel_deposit(token_network, custom_token):
    def get(channel_identifier, participant, deposit=None):
        balance = custom_token.call().balanceOf(participant)
        deposit = deposit or balance

        while balance < deposit:
            custom_token.transact({'from': participant, 'value': 10 ** 18}).mint()
            balance = custom_token.call().balanceOf(participant)

        custom_token.transact({'from': participant}).approve(token_network.address, deposit)

        txn_hash = token_network.transact({'from': participant}).setDeposit(
            channel_identifier,
            participant,
            deposit
        )
        return txn_hash
    return get


@pytest.fixture()
def create_balance_proof(token_network, get_private_key):
    def get(
            channel_identifier,
            participant,
            transferred_amount=0,
            locked_amount=0,
            nonce=0,
            locksroot=None,
            additional_hash=None,
            v=27
    ):
        private_key = get_private_key(participant)
        locksroot = locksroot or b'\x00' * 32
        additional_hash = additional_hash or b'\x00' * 32

        balance_hash = hash_balance_data(transferred_amount, locked_amount, locksroot, additional_hash)

        signature = sign_balance_proof(
            private_key,
            token_network.address,
            int(token_network.call().chain_id()),
            channel_identifier,
            nonce,
            balance_hash,
            v
        )
        return (
            channel_identifier,
            nonce,
            balance_hash,
            signature
        )
    return get
