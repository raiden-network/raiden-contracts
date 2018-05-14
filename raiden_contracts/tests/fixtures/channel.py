import pytest
from raiden_contracts.utils.config import (
    C_TOKEN_NETWORK,
    SETTLE_TIMEOUT_MIN,
    CHANNEL_STATE_OPEN,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED
)
from raiden_contracts.utils.sign import (
    sign_balance_proof,
    hash_balance_data,
    sign_balance_proof_update_message,
    sign_cooperative_settle_message,
    sign_withdraw_message
)
from .token_network import *  # flake8: noqa
from .secret_registry import *  # flake8: noqa
from .config import fake_bytes
from eth_utils import denoms


@pytest.fixture()
def create_channel(token_network):
    def get(A, B, settle_timeout=SETTLE_TIMEOUT_MIN):
        # Make sure there is no channel data on chain
        (_, channel_settle_timeout, channel_state) = token_network.call().getChannelInfo(A, B)
        assert channel_settle_timeout == 0
        assert channel_state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED

        # Open the channel and retrieve the channel identifier
        txn_hash = token_network.transact().openChannel(A, B, settle_timeout)

        # Test the channel state on chain
        (channel_identifier, channel_settle_timeout, channel_state) = token_network.call().getChannelInfo(A, B)
        assert channel_settle_timeout == settle_timeout
        assert channel_state == CHANNEL_STATE_OPEN

        return (channel_identifier, txn_hash)
    return get


@pytest.fixture()
def assign_tokens(token_network, custom_token):
    def get(participant, deposit):
        balance = custom_token.call().balanceOf(participant)
        deposit = deposit or balance

        while balance < deposit:
            custom_token.transact({'from': participant, 'value': 100 * denoms.finney}).mint()
            balance = custom_token.call().balanceOf(participant)

        custom_token.transact({'from': participant}).approve(token_network.address, deposit)
    return get


@pytest.fixture()
def channel_deposit(token_network, assign_tokens):
    def get(participant, deposit, partner, tx_from=None):
        tx_from = tx_from or participant
        assign_tokens(tx_from, deposit)

        txn_hash = token_network.transact({'from': tx_from}).setDeposit(
            participant,
            deposit,
            partner
        )
        return txn_hash
    return get


@pytest.fixture()
def create_channel_and_deposit(create_channel, channel_deposit):
    def get(participant1, participant2, deposit1=0, deposit2=0, settle_timeout=SETTLE_TIMEOUT_MIN):
        channel_identifier = create_channel(participant1, participant2, settle_timeout)[0]

        if deposit1 > 0:
            channel_deposit(participant1, deposit1, participant2)
        if deposit2 > 0:
            channel_deposit(participant2, deposit2, participant1)
        return channel_identifier
    return get


@pytest.fixture()
def withdraw_channel(token_network, create_withdraw_signatures):
    def get(participant, withdraw_amount, partner, delegate=None):
        delegate = delegate or participant
        channel_identifier = token_network.call().getChannelIdentifier(participant, partner)

        (signature_participant, signature_partner) = create_withdraw_signatures(
            [participant, partner],
            channel_identifier,
            participant, withdraw_amount
        )
        txn_hash = token_network.transact({'from': delegate}).withdraw(
            participant, withdraw_amount,
            partner,
            signature_participant,
            signature_partner
        )
        return txn_hash
    return get


@pytest.fixture()
def close_and_update_channel(
        web3,
        token_network,
        create_channel_and_deposit,
        create_balance_proof,
        create_balance_proof_update_signature
):
    def get(
            participant1,
            transferred_amount1,
            locked_amount1,
            locksroot1,
            participant2,
            transferred_amount2,
            locked_amount2,
            locksroot2,
    ):
        nonce1 = 5
        nonce2 = 7
        additional_hash1 = fake_bytes(32)
        additional_hash2 = fake_bytes(32)

        channel_identifier = token_network.call().getChannelIdentifier(participant1, participant2)

        balance_proof_1 = create_balance_proof(
            channel_identifier,
            participant1,
            transferred_amount1,
            locked_amount1,
            nonce1,
            locksroot1,
            additional_hash1
        )
        balance_proof_2 = create_balance_proof(
            channel_identifier,
            participant2,
            transferred_amount2,
            locked_amount2,
            nonce2,
            locksroot2,
            additional_hash2
        )
        balance_proof_update_signature_2 = create_balance_proof_update_signature(
            participant2,
            channel_identifier,
            *balance_proof_1
        )

        token_network.transact({'from': participant1}).closeChannel(
            participant2,
            *balance_proof_2
        )

        token_network.transact({'from': participant2}).updateNonClosingBalanceProof(
            participant1, participant2,
            *balance_proof_1,
            balance_proof_update_signature_2
        )
    return get


@pytest.fixture()
def create_settled_channel(
        web3,
        token_network,
        create_channel_and_deposit,
        close_and_update_channel
):
    def get(
            participant1,
            locked_amount1,
            locksroot1,
            participant2,
            locked_amount2,
            locksroot2,
            settle_timeout=SETTLE_TIMEOUT_MIN,
    ):
        transferred_amount1 = 5
        transferred_amount2 = 40
        deposit1 = locked_amount1 + transferred_amount1 - 5
        deposit2 = locked_amount2 + transferred_amount2 + 5

        channel_identifier = create_channel_and_deposit(
            participant1,
            participant2,
            deposit1,
            deposit2,
            settle_timeout
        )

        close_and_update_channel(
            participant1,
            transferred_amount1,
            locked_amount1,
            locksroot1,
            participant2,
            transferred_amount2,
            locked_amount2,
            locksroot2
        )

        web3.testing.mine(settle_timeout)
        token_network.transact({'from': participant1}).settleChannel(
            participant1,
            transferred_amount1,
            locked_amount1,
            locksroot1,
            participant2,
            transferred_amount2,
            locked_amount2,
            locksroot2
        )
        return channel_identifier

    return get


@pytest.fixture()
def reveal_secrets(web3, secret_registry):
    def get(tx_from, transfers):
        for (_, _, secrethash, secret) in transfers:
            secret_registry.transact({'from': tx_from}).registerSecret(secret)
            assert secret_registry.call().getSecretRevealBlockHeight(secrethash) == web3.eth.blockNumber
    return get


@pytest.fixture()
def cooperative_settle_state_tests(custom_token, token_network):
    def get(
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
        (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
        assert settle_block_number == 0  # settle_block_number
        assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED  # state

        # Make sure participant data has been removed
        (
            A_deposit,
            A_withdrawn,
            A_is_the_closer,
            A_balance_hash,
            A_nonce
        ) = token_network.call().getChannelParticipantInfo(A, B)
        assert A_deposit == 0
        assert A_withdrawn == 0
        assert A_is_the_closer == 0
        assert A_balance_hash == fake_bytes(32)
        assert A_nonce == 0

        (
            B_deposit,
            B_withdrawn,
            B_is_the_closer,
            B_balance_hash,
            B_nonce
        ) = token_network.call().getChannelParticipantInfo(B, A)
        assert B_deposit == 0
        assert B_withdrawn == 0
        assert B_is_the_closer == 0
        assert B_balance_hash == fake_bytes(32)
        assert B_nonce == 0
    return get


@pytest.fixture()
def settle_state_tests(token_network, cooperative_settle_state_tests):
    def get(
            A, balance_A, locksroot_A, locked_amount_A,
            B, balance_B, locksroot_B, locked_amount_B,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
    ):
        cooperative_settle_state_tests(
            A, balance_A,
            B, balance_B,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
        )

        locked_amount1 = token_network.call().getParticipantLockedAmount(A, B, locksroot_A)
        assert locked_amount1 == locked_amount_A

        locked_amount2 = token_network.call().getParticipantLockedAmount(A, B, locksroot_B)
        assert locked_amount2 == locked_amount_B
    return get


@pytest.fixture()
def withdraw_state_tests(custom_token, token_network):
    def get(
            participant,
            deposit_participant,
            total_withdrawn_participant,
            pre_withdrawn_participant,
            pre_balance_participant,
            partner,
            deposit_partner,
            total_withdrawn_partner,
            pre_balance_partner,
            pre_balance_contract,
            delegate=None,
            pre_balance_delegate=None
    ):
        current_withdrawn_participant = total_withdrawn_participant - pre_withdrawn_participant
        (_, _, state) = token_network.call().getChannelInfo(participant, partner)
        assert state == CHANNEL_STATE_OPEN

        (
            deposit,
            withdrawn_amount,
            is_the_closer,
            balance_hash,
            nonce
        ) = token_network.call().getChannelParticipantInfo(participant, partner)
        assert deposit == deposit_participant
        assert withdrawn_amount == total_withdrawn_participant
        assert is_the_closer is False
        assert balance_hash == fake_bytes(32)
        assert nonce == 0

        (
            deposit,
            withdrawn_amount,
            is_the_closer,
            balance_hash,
            nonce
        ) = token_network.call().getChannelParticipantInfo(partner, participant)
        assert deposit == deposit_partner
        assert withdrawn_amount == total_withdrawn_partner
        assert is_the_closer is False
        assert balance_hash == fake_bytes(32)
        assert nonce == 0

        balance_participant = custom_token.call().balanceOf(participant)
        balance_partner = custom_token.call().balanceOf(partner)
        balance_contract = custom_token.call().balanceOf(token_network.address)
        assert balance_participant == pre_balance_participant + current_withdrawn_participant
        assert balance_partner == pre_balance_partner
        assert balance_contract == pre_balance_contract - current_withdrawn_participant

        if delegate is not None:
            balance_delegate = custom_token.call().balanceOf(delegate)
            assert balance_delegate == balance_delegate
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
            v=27,
            signer=None
    ):
        private_key = get_private_key(signer or participant)
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


@pytest.fixture()
def create_withdraw_signatures(token_network, get_private_key):
    def get(
            participants_to_sign,
            channel_identifier,
            participant_who_withdraws,
            amount_to_withdraw,
            token_network_address=None,
            v=27
    ):
        if token_network_address is None:
            token_network_address = token_network.address

        signatures = []
        for participant in participants_to_sign:
            private_key = get_private_key(participant)
            signature = sign_withdraw_message(
                private_key,
                token_network_address,
                int(token_network.call().chain_id()),
                channel_identifier,
                participant_who_withdraws,
                amount_to_withdraw,
                v
            )
            signatures.append(signature)
        return signatures
    return get
