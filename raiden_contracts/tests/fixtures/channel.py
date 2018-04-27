import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK, SETTLE_TIMEOUT_MIN, CHANNEL_STATE_NONEXISTENT_OR_SETTLED
from raiden_contracts.utils.sign import (
    sign_balance_proof,
    hash_balance_data,
    sign_balance_proof_update_message,
    sign_cooperative_settle_message
)
from .token_network import *  # flake8: noqa
from .secret_registry import *  # flake8: noqa
from .config import fake_bytes


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
def create_channel_and_deposit(create_channel, channel_deposit):
    def get(participant1, participant2, deposit1=0, deposit2=0, settle_timeout=SETTLE_TIMEOUT_MIN):
        channel_identifier = create_channel(participant1, participant2, settle_timeout)

        if deposit1 > 0:
            channel_deposit(channel_identifier, participant1, deposit1)
        if deposit2 > 0:
            channel_deposit(channel_identifier, participant2, deposit2)
        return channel_identifier
    return get


@pytest.fixture()
def cooperative_settle_state_tests(custom_token, token_network):
    def get(
            channel_identifier,
            A, balance_A,
            B, balance_B,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
    ):
        # Make sure the correct amount of tokens has been transferred
        account_balance_A = custom_token.call().balanceOf(A)
        account_balance_B = custom_token.call().balanceOf(B)
        balance_contract = custom_token.call().balanceOf(token_network.address)
        assert account_balance_A == pre_account_balance_A + balance_A
        assert account_balance_B == pre_account_balance_B + balance_B
        assert balance_contract == pre_balance_contract - balance_A - balance_B

        # Make sure channel data has been removed
        (settle_block_number, state) = token_network.call().getChannelInfo(1)
        assert settle_block_number == 0  # settle_block_number
        assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED  # state

        # Make sure participant data has been removed
        (
            A_deposit,
            A_is_initialized,
            A_is_the_closer,
            A_locksroot,
            A_locked_amount
        ) = token_network.call().getChannelParticipantInfo(1, A, B)
        assert A_deposit == 0
        assert A_is_initialized == 0
        assert A_is_the_closer == 0

        # Make sure there is no balance data
        assert A_locksroot == fake_bytes(32)
        assert A_locked_amount == 0

        (
            B_deposit,
            B_is_initialized,
            B_is_the_closer,
            B_locksroot,
            B_locked_amount
        ) = token_network.call().getChannelParticipantInfo(1, B, A)
        assert B_deposit == 0
        assert B_is_initialized == 0
        assert B_is_the_closer == 0

        # Make sure there is no balance data
        assert B_locksroot == fake_bytes(32)
        assert B_locked_amount == 0
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
def create_cooperative_settle_signatures(token_network, get_private_key):
    def get(
            participants_to_sign,
            channel_identifier,
            participant1_address,
            participant1_balance,
            participant2_address,
            participant2_balance,
            v=27
    ):
        signatures = []
        for participant in participants_to_sign:
            private_key = get_private_key(participant)
            signature = sign_cooperative_settle_message(
                private_key,
                token_network.address,
                int(token_network.call().chain_id()),
                channel_identifier,
                participant1_address,
                participant1_balance,
                participant2_address,
                participant2_balance,
                v
            )
            signatures.append(signature)
        return signatures
    return get
