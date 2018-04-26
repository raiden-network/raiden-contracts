import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK, SETTLE_TIMEOUT_MIN
from raiden_contracts.utils.sign import (
    sign_balance_proof,
    hash_balance_data,
    sign_balance_proof_update_message,
    sign_cooperative_settle_message
)
from .token_network import *  # flake8: noqa
from .secret_registry import *  # flake8: noqa


@pytest.fixture()
def create_channel(token_network):
    def get(A, B, settle_timeout=SETTLE_TIMEOUT_MIN):
        txn_hash = token_network.transact().openChannel(A, B, settle_timeout)
        channel_identifier = token_network.call().last_channel_index()
        assert token_network.call().getChannelInfo(channel_identifier)[0] == settle_timeout
        assert token_network.call().getChannelParticipantInfo(channel_identifier, A, B)[1] is True
        assert token_network.call().getChannelParticipantInfo(channel_identifier, B, A)[1] is True
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

        balance_hash = hash_balance_data(transferred_amount, locked_amount, locksroot)

        signature = sign_balance_proof(
            private_key,
            token_network.address,
            int(token_network.call().chain_id()),
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            v
        )
        return (
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            signature
        )
    return get


@pytest.fixture()
def create_balance_proof_update_signature(token_network, get_private_key):
    def get(
            participant,
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature,
            v=27
    ):
        private_key = get_private_key(participant)

        non_closing_signature = sign_balance_proof_update_message(
            private_key,
            token_network.address,
            int(token_network.call().chain_id()),
            channel_identifier,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature,
            v
        )
        return non_closing_signature
    return get


@pytest.fixture()
def create_cooperative_settle_signature(token_network, get_private_key):
    def get(
            channel_identifier,
            participant,
            participant1_balance,
            participant2_balance,
            v=27
    ):
        private_key = get_private_key(participant)

        signature = sign_cooperative_settle_message(
            private_key,
            token_network.address,
            int(token_network.call().chain_id()),
            channel_identifier,
            participant1_balance,
            participant2_balance,
            v
        )
        return signature
    return get
