import pytest
from eth_tester.exceptions import TransactionFailed
from collections import namedtuple
from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK,
    TEST_SETTLE_TIMEOUT_MIN,
    CHANNEL_STATE_OPENED,
    CHANNEL_STATE_CLOSED,
    CHANNEL_STATE_SETTLED,
)
from raiden_contracts.utils.sign import (
    sign_balance_proof,
    hash_balance_data,
    sign_balance_proof_update_message,
    sign_cooperative_settle_message,
    sign_withdraw_message,
)
from raiden_contracts.tests.utils import (
    get_settlement_amounts,
    get_onchain_settlement_amounts,
    ChannelValues,
    get_participants_hash,
)
from .token_network import *  # flake8: noqa
from .secret_registry import *  # flake8: noqa
from .config import fake_bytes


@pytest.fixture()
def create_channel(token_network):
    def get(A, B, settle_timeout=TEST_SETTLE_TIMEOUT_MIN):
        # Make sure there is no channel existent on chain
        assert token_network.functions.getChannelIdentifier(A, B).call() == 0

        # Open the channel and retrieve the channel identifier
        txn_hash = token_network.functions.openChannel(A, B, settle_timeout).transact()

        # Get the channel identifier
        channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()

        # Test the channel state on chain
        (channel_settle_timeout, channel_state) = token_network.functions.getChannelInfo(channel_identifier).call()
        assert channel_settle_timeout == settle_timeout
        assert channel_state == CHANNEL_STATE_OPENED

        return (channel_identifier, txn_hash)
    return get


@pytest.fixture()
def assign_tokens(owner, token_network, custom_token):
    def get(participant, deposit):
        balance = custom_token.functions.balanceOf(participant).call()
        owner_balance = custom_token.functions.balanceOf(owner).call()
        amount = max(deposit - balance, 0)
        transfer_from_owner = min(amount, owner_balance)

        custom_token.functions.transfer(participant, transfer_from_owner).transact({'from': owner})
        assert custom_token.functions.balanceOf(participant).call() >= transfer_from_owner

        if amount > owner_balance:
            minted = amount - owner_balance
            custom_token.functions.mint(minted).transact({'from': participant})
        assert custom_token.functions.balanceOf(participant).call() >= deposit
        custom_token.functions.approve(token_network.address, deposit).transact({'from': participant})
        assert custom_token.functions.allowance(
            participant,
            token_network.address
        ).call() >= deposit
    return get


@pytest.fixture()
def channel_deposit(token_network, assign_tokens):
    def get(channel_identifier, participant, deposit, partner, tx_from=None):
        tx_from = tx_from or participant
        assign_tokens(tx_from, deposit)

        txn_hash = token_network.functions.setTotalDeposit(
            channel_identifier,
            participant,
            deposit,
            partner
        ).transact({'from': tx_from})
        return txn_hash
    return get


@pytest.fixture()
def create_channel_and_deposit(create_channel, channel_deposit):
    def get(participant1, participant2, deposit1=0, deposit2=0, settle_timeout=TEST_SETTLE_TIMEOUT_MIN):
        channel_identifier = create_channel(participant1, participant2, settle_timeout)[0]

        if deposit1 > 0:
            channel_deposit(channel_identifier, participant1, deposit1, participant2)
        if deposit2 > 0:
            channel_deposit(channel_identifier, participant2, deposit2, participant1)
        return channel_identifier
    return get


@pytest.fixture()
def withdraw_channel(token_network, create_withdraw_signatures):
    def get(channel_identifier, participant, withdraw_amount, partner, delegate=None):
        delegate = delegate or participant
        channel_identifier = token_network.functions.getChannelIdentifier(participant, partner).call()

        (signature_participant, signature_partner) = create_withdraw_signatures(
            [participant, partner],
            channel_identifier,
            participant, withdraw_amount
        )
        txn_hash = token_network.functions.setTotalWithdraw(
            channel_identifier,
            participant,
            withdraw_amount,
            partner,
            signature_participant,
            signature_partner
        ).transact({'from': delegate})
        return txn_hash
    return get


@pytest.fixture()
def close_and_update_channel(
        token_network,
        create_balance_proof,
        create_balance_proof_update_signature
):
    def get(
            channel_identifier,
            participant1,
            participant1_values,
            participant2,
            participant2_values,
    ):
        nonce1 = 5
        nonce2 = 7
        additional_hash1 = fake_bytes(32)
        additional_hash2 = fake_bytes(32)

        balance_proof_1 = create_balance_proof(
            channel_identifier,
            participant1,
            participant1_values.transferred,
            participant1_values.locked,
            nonce1,
            participant1_values.locksroot,
            additional_hash1
        )
        balance_proof_2 = create_balance_proof(
            channel_identifier,
            participant2,
            participant2_values.transferred,
            participant2_values.locked,
            nonce2,
            participant2_values.locksroot,
            additional_hash2
        )
        balance_proof_update_signature_2 = create_balance_proof_update_signature(
            participant2,
            channel_identifier,
            *balance_proof_1
        )

        token_network.functions.closeChannel(
            channel_identifier,
            participant2,
            *balance_proof_2
        ).transact({'from': participant1})

        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            participant1,
            participant2,
            *balance_proof_1,
            balance_proof_update_signature_2
        ).transact({'from': participant2})
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
            settle_timeout=TEST_SETTLE_TIMEOUT_MIN,
    ):
        participant1_values = ChannelValues(
            transferred=5,
            locked=locked_amount1,
            locksroot=locksroot1,
        )
        participant2_values = ChannelValues(
            transferred=40,
            locked=locked_amount2,
            locksroot=locksroot2,
        )

        participant1_values.deposit = (
            participant1_values.locked +
            participant1_values.transferred -
            5
        )
        participant2_values.deposit = (
            participant2_values.locked +
            participant2_values.transferred +
            5
        )

        channel_identifier = create_channel_and_deposit(
            participant1,
            participant2,
            participant1_values.deposit,
            participant2_values.deposit,
            settle_timeout
        )

        close_and_update_channel(
            channel_identifier,
            participant1,
            participant1_values,
            participant2,
            participant2_values,
        )

        web3.testing.mine(settle_timeout)

        call_settle(
            token_network,
            channel_identifier,
            participant1,
            participant1_values,
            participant2,
            participant2_values
        )

        return channel_identifier

    return get


@pytest.fixture()
def reveal_secrets(web3, secret_registry_contract):
    def get(tx_from, transfers):
        for (_, _, secrethash, secret) in transfers:
            secret_registry_contract.functions.registerSecret(secret).transact({'from': tx_from})
            assert secret_registry_contract.functions.getSecretRevealBlockHeight(secrethash).call() == web3.eth.blockNumber
    return get


@pytest.fixture()
def common_settle_state_tests(custom_token, token_network):
    def get(
            channel_identifier,
            A,
            balance_A,
            B,
            balance_B,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
    ):
        # Make sure the correct amount of tokens has been transferred
        account_balance_A = custom_token.functions.balanceOf(A).call()
        account_balance_B = custom_token.functions.balanceOf(B).call()
        balance_contract = custom_token.functions.balanceOf(token_network.address).call()
        assert account_balance_A == pre_account_balance_A + balance_A
        assert account_balance_B == pre_account_balance_B + balance_B
        assert balance_contract == pre_balance_contract - balance_A - balance_B

        # Make sure channel data has been removed
        assert token_network.functions.participants_hash_to_channel_identifier(
            get_participants_hash(A, B)
        ).call() == 0

        (settle_block_number, state) = token_network.functions.getChannelInfo(channel_identifier).call()
        assert settle_block_number == 0  # settle_block_number
        assert state == CHANNEL_STATE_SETTLED  # state

        # Make sure participant data has been removed
        (
            A_deposit,
            A_withdrawn,
            A_is_the_closer,
            A_balance_hash,
            A_nonce
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A).call()
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
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B).call()
        assert B_deposit == 0
        assert B_withdrawn == 0
        assert B_is_the_closer == 0
        assert B_balance_hash == fake_bytes(32)
        assert B_nonce == 0
    return get


@pytest.fixture()
def update_state_tests(token_network, get_block):
    def get(
            channel_identifier,
            A,
            balance_proof_A,
            B,
            balance_proof_B,
            settle_timeout,
            txn_hash1,
    ):
        (settle_block_number, state) = token_network.functions.getChannelInfo(channel_identifier).call()

        assert settle_block_number == settle_timeout + get_block(txn_hash1)  # settle_block_number
        assert state == CHANNEL_STATE_CLOSED  # state

        (
            _,
            _,
            A_is_the_closer,
            A_balance_hash,
            A_nonce
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A).call()
        assert A_is_the_closer is True
        assert A_balance_hash == balance_proof_A[0]
        assert A_nonce == 5

        (
            _,
            _,
            B_is_the_closer,
            B_balance_hash,
            B_nonce
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B).call()
        assert B_is_the_closer is False
        assert B_balance_hash == balance_proof_B[0]
        assert B_nonce == 3
    return get


@pytest.fixture()
def settle_state_tests(token_network, common_settle_state_tests):
    def get(
            channel_identifier,
            A,
            values_A,
            B,
            values_B,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
    ):
        # Calculate how much A and B should receive
        settlement = get_settlement_amounts(values_A, values_B)
        # Calculate how much A and B receive according to onchain computation
        on_chain_settlement = get_onchain_settlement_amounts(values_A, values_B)

        common_settle_state_tests(
            channel_identifier,
            A,
            settlement.participant1_balance,
            B,
            settlement.participant2_balance,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
        )
        common_settle_state_tests(
            channel_identifier,
            A,
            on_chain_settlement.participant1_balance,
            B,
            on_chain_settlement.participant2_balance,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
        )

        locked_amount1 = token_network.functions.getParticipantLockedAmount(A, B, values_A.locksroot).call()
        assert locked_amount1 == settlement.participant1_locked
        assert locked_amount1 == on_chain_settlement.participant1_locked

        locked_amount2 = token_network.functions.getParticipantLockedAmount(B, A, values_B.locksroot).call()
        assert locked_amount2 == settlement.participant2_locked
        assert locked_amount2 == on_chain_settlement.participant2_locked

    return get


@pytest.fixture()
def unlock_state_tests(token_network):
    def get(
            A,
            locked_A,
            locksroot_A,
            B,
            locked_B,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract
    ):
        account_balance_A = custom_token.functions.balanceOf(A).call()
        account_balance_B = custom_token.functions.balanceOf(B).call()
        balance_contract = custom_token.functions.balanceOf(token_network.address).call()
        assert account_balance_A == pre_account_balance_A + locked_A
        assert account_balance_B == pre_account_balance_B + locked_B
        assert balance_contract == pre_balance_contract - locked_A - locked_B

        assert token_network.functions.getParticipantLockedAmount(
            A,
            B,
            locksroot_A
        ).call() == 0
    return get

@pytest.fixture()
def withdraw_state_tests(custom_token, token_network):
    def get(
            channel_identifier,
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
        (_, state) = token_network.functions.getChannelInfo(channel_identifier).call()
        assert state == CHANNEL_STATE_OPENED

        (
            deposit,
            withdrawn_amount,
            is_the_closer,
            balance_hash,
            nonce
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, participant).call()
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
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, partner).call()
        assert deposit == deposit_partner
        assert withdrawn_amount == total_withdrawn_partner
        assert is_the_closer is False
        assert balance_hash == fake_bytes(32)
        assert nonce == 0

        balance_participant = custom_token.functions.balanceOf(participant).call()
        balance_partner = custom_token.functions.balanceOf(partner).call()
        balance_contract = custom_token.functions.balanceOf(token_network.address).call()
        assert balance_participant == pre_balance_participant + current_withdrawn_participant
        assert balance_partner == pre_balance_partner
        assert balance_contract == pre_balance_contract - current_withdrawn_participant

        if delegate is not None:
            balance_delegate = custom_token.functions.balanceOf(delegate).call()
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
            signer=None,
            other_token_network=None
    ):
        _token_network = other_token_network or token_network
        private_key = get_private_key(signer or participant)
        locksroot = locksroot or b'\x00' * 32
        additional_hash = additional_hash or b'\x00' * 32

        balance_hash = hash_balance_data(transferred_amount, locked_amount, locksroot)

        signature = sign_balance_proof(
            private_key,
            _token_network.address,
            int(_token_network.functions.chain_id().call()),
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
            v=27,
            other_token_network=None
    ):
        _token_network = other_token_network or token_network
        private_key = get_private_key(participant)

        non_closing_signature = sign_balance_proof_update_message(
            private_key,
            _token_network.address,
            int(_token_network.functions.chain_id().call()),
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
            v=27,
            other_token_network=None
    ):
        _token_network = other_token_network or token_network
        signatures = []
        for participant in participants_to_sign:
            private_key = get_private_key(participant)
            signature = sign_cooperative_settle_message(
                private_key,
                _token_network.address,
                int(_token_network.functions.chain_id().call()),
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
                int(token_network.functions.chain_id().call()),
                channel_identifier,
                participant_who_withdraws,
                amount_to_withdraw,
                v
            )
            signatures.append(signature)
        return signatures
    return get


def call_settle(token_network, channel_identifier, A, vals_A, B, vals_B):
    assert vals_B.transferred + vals_B.locked >= vals_A.transferred + vals_A.locked

    if vals_B.transferred != vals_A.transferred:
        with pytest.raises(TransactionFailed):
            token_network.functions.settleChannel(
                channel_identifier,
                B,
                vals_B.transferred,
                vals_B.locked,
                vals_B.locksroot,
                A,
                vals_A.transferred,
                vals_A.locked,
                vals_A.locksroot,
            ).transact({'from': A})

    token_network.functions.settleChannel(
        channel_identifier,
        A,
        vals_A.transferred,
        vals_A.locked,
        vals_A.locksroot,
        B,
        vals_B.transferred,
        vals_B.locked,
        vals_B.locksroot
    ).transact({'from': A})
