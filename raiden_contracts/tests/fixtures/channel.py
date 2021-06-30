from typing import Callable, Collection, List, Optional, Tuple

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_typing import HexAddress
from hexbytes import HexBytes
from web3 import Web3
from web3.contract import Contract
from web3.types import Nonce

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ChannelState, MessageTypeId
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_BALANCE_HASH,
    EMPTY_SIGNATURE,
    LOCKSROOT_OF_NO_LOCKS,
    NONEXISTENT_LOCKSROOT,
    ChannelValues,
    LockedAmounts,
    call_and_transact,
    fake_bytes,
    get_onchain_settlement_amounts,
    get_participants_hash,
    get_settlement_amounts,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.tests.utils.constants import DEPLOYER_ADDRESS, OnchainBalanceProof
from raiden_contracts.utils.proofs import (
    hash_balance_data,
    sign_balance_proof,
    sign_balance_proof_message,
    sign_withdraw_message,
)
from raiden_contracts.utils.type_aliases import (
    AdditionalHash,
    BalanceHash,
    BlockExpiration,
    ChannelID,
    Locksroot,
    Signature,
    TokenAmount,
)


@pytest.fixture(scope="session")
def create_channel(token_network: Contract) -> Callable:
    def get(A: HexAddress, B: HexAddress, settle_timeout: int = TEST_SETTLE_TIMEOUT_MIN) -> Tuple:
        # Make sure there is no channel existent on chain
        assert token_network.functions.getChannelIdentifier(A, B).call() == 0

        # Open the channel and retrieve the channel identifier
        txn_hash = call_and_transact(
            token_network.functions.openChannel(
                participant1=A, participant2=B, settle_timeout=settle_timeout
            )
        )

        # Get the channel identifier
        channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()

        # Test the channel state on chain
        (
            channel_settle_timeout,
            channel_state,
        ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
        assert channel_settle_timeout == settle_timeout
        assert channel_state == ChannelState.OPENED

        return (channel_identifier, txn_hash)

    return get


@pytest.fixture()
def assign_tokens(token_network: Contract, custom_token: Contract) -> Callable:
    def get(participant: HexAddress, deposit: int) -> None:
        owner = DEPLOYER_ADDRESS
        balance = custom_token.functions.balanceOf(participant).call()
        owner_balance = custom_token.functions.balanceOf(owner).call()
        amount = max(deposit - balance, 0)
        transfer_from_owner = min(amount, owner_balance)

        call_and_transact(
            custom_token.functions.transfer(_to=participant, _value=transfer_from_owner),
            {"from": owner},
        )
        assert custom_token.functions.balanceOf(participant).call() >= transfer_from_owner

        if amount > owner_balance:
            minted = amount - owner_balance
            call_and_transact(custom_token.functions.mint(minted), {"from": participant})
        assert custom_token.functions.balanceOf(participant).call() >= deposit
        call_and_transact(
            custom_token.functions.approve(_spender=token_network.address, _value=deposit),
            {"from": participant},
        )
        assert (
            custom_token.functions.allowance(
                _owner=participant, _spender=token_network.address
            ).call()
            >= deposit
        )

    return get


@pytest.fixture()
def channel_deposit(token_network: Contract, assign_tokens: Callable) -> Callable:
    def get(
        channel_identifier: int,
        participant: HexAddress,
        deposit: int,
        partner: HexAddress,
        tx_from: Optional[HexAddress] = None,
    ) -> HexBytes:
        tx_from = tx_from or participant
        assign_tokens(tx_from, deposit)

        txn_hash = call_and_transact(
            token_network.functions.setTotalDeposit(
                channel_identifier=channel_identifier,
                participant=participant,
                total_deposit=deposit,
                partner=partner,
            ),
            {"from": tx_from},
        )
        return txn_hash

    return get


@pytest.fixture()
def create_channel_and_deposit(create_channel: Callable, channel_deposit: Callable) -> Callable:
    def get(
        participant1: HexAddress,
        participant2: HexAddress,
        deposit1: int = 0,
        deposit2: int = 0,
        settle_timeout: int = TEST_SETTLE_TIMEOUT_MIN,
    ) -> int:
        channel_identifier = create_channel(participant1, participant2, settle_timeout)[0]

        if deposit1 > 0:
            channel_deposit(channel_identifier, participant1, deposit1, participant2)
        if deposit2 > 0:
            channel_deposit(channel_identifier, participant2, deposit2, participant1)
        return channel_identifier

    return get


@pytest.fixture()
def withdraw_channel(token_network: Contract, create_withdraw_signatures: Callable) -> Callable:
    def get(
        channel_identifier: int,
        participant: HexAddress,
        withdraw_amount: int,
        expiration_block: int,
        partner: HexAddress,
        delegate: Optional[HexAddress] = None,
    ) -> HexBytes:
        delegate = delegate or participant
        channel_identifier = token_network.functions.getChannelIdentifier(
            participant, partner
        ).call()

        (signature_participant, signature_partner) = create_withdraw_signatures(
            [participant, partner],
            channel_identifier,
            participant,
            withdraw_amount,
            expiration_block,
        )
        txn_hash = call_and_transact(
            token_network.functions.setTotalWithdraw(
                channel_identifier,
                participant,
                withdraw_amount,
                expiration_block,
                signature_participant,
                signature_partner,
            ),
            {"from": delegate},
        )
        return txn_hash

    return get


@pytest.fixture()
def cooperative_settle_channel(
    token_network: Contract, create_withdraw_signatures: Callable
) -> Callable:
    def get(
        channel_identifier: int,
        participant: HexAddress,
        partner: HexAddress,
        withdraw_amount_participant: int,
        withdraw_amount_partner: int,
        expiration_block: int,
        delegate: Optional[HexAddress] = None,
    ) -> HexBytes:
        delegate = delegate or participant
        channel_identifier = token_network.functions.getChannelIdentifier(
            participant, partner
        ).call()

        (signature_A1, signature_B1) = create_withdraw_signatures(
            [participant, partner],
            channel_identifier,
            participant,
            withdraw_amount_participant,
            expiration_block,
        )
        (signature_A2, signature_B2) = create_withdraw_signatures(
            [participant, partner],
            channel_identifier,
            partner,
            withdraw_amount_partner,
            expiration_block,
        )

        txn_hash = call_and_transact(
            token_network.functions.cooperativeSettle(
                channel_identifier,
                (
                    participant,
                    withdraw_amount_participant,
                    expiration_block,
                    signature_A1,
                    signature_B1,
                ),
                (partner, withdraw_amount_partner, expiration_block, signature_B2, signature_A2),
            ),
            {"from": delegate},
        )
        return txn_hash

    return get


@pytest.fixture()
def close_and_update_channel(
    token_network: Contract,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> Callable:
    def get(
        channel_identifier: int,
        participant1: HexAddress,
        participant1_values: ChannelValues,
        participant2: HexAddress,
        participant2_values: ChannelValues,
    ) -> None:
        nonce1 = 5
        nonce2 = 7
        additional_hash1 = fake_bytes(32)
        additional_hash2 = fake_bytes(32)

        balance_proof_1 = create_balance_proof(
            channel_identifier,
            participant1,
            participant1_values.transferred,
            participant1_values.locked_amounts.locked,
            nonce1,
            participant1_values.locksroot,
            additional_hash1,
        )
        balance_proof_2 = create_balance_proof(
            channel_identifier,
            participant2,
            participant2_values.transferred,
            participant2_values.locked_amounts.locked,
            nonce2,
            participant2_values.locksroot,
            additional_hash2,
        )
        balance_proof_close_signature_1 = create_balance_proof_countersignature(
            participant=participant1,
            channel_identifier=channel_identifier,
            msg_type=MessageTypeId.BALANCE_PROOF,
            **balance_proof_2._asdict(),
        )
        balance_proof_update_signature_2 = create_balance_proof_countersignature(
            participant=participant2,
            channel_identifier=channel_identifier,
            msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
            **balance_proof_1._asdict(),
        )

        call_and_transact(
            token_network.functions.closeChannel(
                channel_identifier,
                participant2,
                participant1,
                *balance_proof_2._asdict().values(),
                balance_proof_close_signature_1,
            ),
            {"from": participant1},
        )

        call_and_transact(
            token_network.functions.updateNonClosingBalanceProof(
                channel_identifier,
                participant1,
                participant2,
                *balance_proof_1._asdict().values(),
                balance_proof_update_signature_2,
            ),
            {"from": participant2},
        )

    return get


@pytest.fixture()
def create_settled_channel(
    web3: Web3,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    close_and_update_channel: Callable,
) -> Callable:
    def get(
        participant1: HexAddress,
        locked_amount1: int,
        locksroot1: bytes,
        participant2: HexAddress,
        locked_amount2: int,
        locksroot2: bytes,
        settle_timeout: int = TEST_SETTLE_TIMEOUT_MIN,
    ) -> int:
        participant1_values = ChannelValues(
            transferred=5,
            locked_amounts=LockedAmounts(claimable_locked=locked_amount1),
            locksroot=locksroot1,
        )
        participant2_values = ChannelValues(
            transferred=40,
            locked_amounts=LockedAmounts(claimable_locked=locked_amount2),
            locksroot=locksroot2,
        )

        participant1_values.deposit = (
            participant1_values.locked_amounts.locked + participant1_values.transferred - 5
        )
        participant2_values.deposit = (
            participant2_values.locked_amounts.locked + participant2_values.transferred + 5
        )

        channel_identifier = create_channel_and_deposit(
            participant1,
            participant2,
            participant1_values.deposit,
            participant2_values.deposit,
            settle_timeout,
        )

        close_and_update_channel(
            channel_identifier,
            participant1,
            participant1_values,
            participant2,
            participant2_values,
        )

        mine_blocks(web3, settle_timeout)

        call_settle(
            token_network,
            channel_identifier,
            participant1,
            participant1_values,
            participant2,
            participant2_values,
        )

        return channel_identifier

    return get


@pytest.fixture()
def reveal_secrets(web3: Web3, secret_registry_contract: Contract) -> Callable:
    def get(tx_from: HexAddress, transfers: List[Tuple]) -> None:
        for (expiration, _, secrethash, secret) in transfers:
            assert web3.eth.block_number < expiration
            call_and_transact(
                secret_registry_contract.functions.registerSecret(secret),
                {"from": tx_from},
            )
            assert (
                secret_registry_contract.functions.getSecretRevealBlockHeight(secrethash).call()
                == web3.eth.block_number
            )

    return get


def common_settle_state_tests(
    custom_token: Contract,
    token_network: Contract,
    channel_identifier: int,
    A: HexAddress,
    balance_A: int,
    B: HexAddress,
    balance_B: int,
    pre_account_balance_A: int,
    pre_account_balance_B: int,
    pre_balance_contract: int,
) -> None:
    # Make sure the correct amount of tokens has been transferred
    account_balance_A = custom_token.functions.balanceOf(A).call()
    account_balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()
    assert account_balance_A == pre_account_balance_A + balance_A
    assert account_balance_B == pre_account_balance_B + balance_B
    assert balance_contract == pre_balance_contract - balance_A - balance_B

    # Make sure channel data has been removed
    assert (
        token_network.functions.participants_hash_to_channel_identifier(
            get_participants_hash(A, B)
        ).call()
        == 0
    )

    # Make sure participant data has been removed
    (
        A_deposit,
        A_withdrawn,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
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
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_deposit == 0
    assert B_withdrawn == 0
    assert B_is_the_closer == 0
    assert B_balance_hash == fake_bytes(32)
    assert B_nonce == 0


@pytest.fixture()
def update_state_tests(token_network: Contract, get_block: Callable) -> Callable:
    def get(
        channel_identifier: int,
        A: HexAddress,
        balance_proof_A: OnchainBalanceProof,
        B: HexAddress,
        balance_proof_B: OnchainBalanceProof,
        settle_timeout: int,
        txn_hash1: str,
    ) -> None:
        (settle_block_number, state) = token_network.functions.getChannelInfo(
            channel_identifier, A, B
        ).call()

        assert settle_block_number == settle_timeout + get_block(txn_hash1)
        assert state == ChannelState.CLOSED

        (
            _,
            _,
            A_is_the_closer,
            A_balance_hash,
            A_nonce,
            A_locksroot,
            A_locked,
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
        assert A_is_the_closer is True
        assert A_balance_hash == balance_proof_A.balance_hash
        assert A_nonce == 5
        assert A_locksroot == NONEXISTENT_LOCKSROOT
        assert A_locked == 0

        (
            _,
            _,
            B_is_the_closer,
            B_balance_hash,
            B_nonce,
            B_locksroot,
            B_locked,
        ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
        assert B_is_the_closer is False
        assert B_balance_hash == balance_proof_B.balance_hash
        assert B_nonce == 3
        assert B_locksroot == NONEXISTENT_LOCKSROOT
        assert B_locked == 0

    return get


@pytest.fixture()
def cooperative_settle_state_tests(token_network: Contract, custom_token: Contract) -> Callable:
    def get(
        channel_identifier: int,
        A: HexAddress,
        balance_A: int,
        B: HexAddress,
        balance_B: int,
        pre_account_balance_A: int,
        pre_account_balance_B: int,
        pre_balance_contract: int,
    ) -> None:
        common_settle_state_tests(
            custom_token,
            token_network,
            channel_identifier,
            A,
            balance_A,
            B,
            balance_B,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract,
        )

        (settle_block_number, state) = token_network.functions.getChannelInfo(
            channel_identifier, A, B
        ).call()
        assert settle_block_number == 0
        assert state == ChannelState.REMOVED

    return get


@pytest.fixture()
def settle_state_tests(token_network: Contract, custom_token: Contract) -> Callable:
    def get(
        channel_identifier: int,
        A: HexAddress,
        values_A: ChannelValues,
        B: HexAddress,
        values_B: ChannelValues,
        pre_account_balance_A: int,
        pre_account_balance_B: int,
        pre_balance_contract: int,
    ) -> None:
        # Calculate how much A and B should receive
        settlement = get_settlement_amounts(values_A, values_B)
        # Calculate how much A and B receive according to onchain computation
        on_chain_settlement = get_onchain_settlement_amounts(values_A, values_B)

        common_settle_state_tests(
            custom_token,
            token_network,
            channel_identifier,
            A,
            settlement.participant1_balance,
            B,
            settlement.participant2_balance,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract,
        )
        common_settle_state_tests(
            custom_token,
            token_network,
            channel_identifier,
            A,
            on_chain_settlement.participant1_balance,
            B,
            on_chain_settlement.participant2_balance,
            pre_account_balance_A,
            pre_account_balance_B,
            pre_balance_contract,
        )

        info_A = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
        (_, _, _, _, _, locksroot_A, locked_amount_A) = info_A
        assert locked_amount_A == settlement.participant1_locked
        assert locked_amount_A == on_chain_settlement.participant1_locked
        if locked_amount_A > 0:
            assert locksroot_A == values_A.locksroot

        info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
        (_, _, _, _, _, locksroot_B, locked_amount_B) = info_B
        assert locked_amount_B == settlement.participant2_locked
        assert locked_amount_B == on_chain_settlement.participant2_locked
        if locked_amount_B > 0:
            assert locksroot_B == values_B.locksroot

        (settle_block_number, state) = token_network.functions.getChannelInfo(
            channel_identifier, A, B
        ).call()
        assert settle_block_number == 0
        if locked_amount_A > 0 or locked_amount_B > 0:
            assert state == ChannelState.SETTLED
        else:
            assert state == ChannelState.REMOVED

    return get


@pytest.fixture()
def unlock_state_tests(custom_token: Contract, token_network: Contract) -> Callable:
    def get(
        A: HexAddress,
        locked_A: int,
        locksroot_A: bytes,
        B: HexAddress,
        locked_B: int,
        pre_account_balance_A: int,
        pre_account_balance_B: int,
        pre_balance_contract: int,
    ) -> None:
        account_balance_A = custom_token.functions.balanceOf(A).call()
        account_balance_B = custom_token.functions.balanceOf(B).call()
        balance_contract = custom_token.functions.balanceOf(token_network.address).call()
        assert account_balance_A == pre_account_balance_A + locked_A
        assert account_balance_B == pre_account_balance_B + locked_B
        assert balance_contract == pre_balance_contract - locked_A - locked_B

        assert token_network.functions.getParticipantLockedAmount(A, B, locksroot_A).call() == 0

    return get


@pytest.fixture()
def withdraw_state_tests(custom_token: Contract, token_network: Contract) -> Callable:
    def get(
        channel_identifier: int,
        participant: HexAddress,
        deposit_participant: int,
        total_withdrawn_participant: int,
        pre_withdrawn_participant: int,
        pre_balance_participant: int,
        partner: HexAddress,
        deposit_partner: HexAddress,
        total_withdrawn_partner: int,
        pre_balance_partner: int,
        pre_balance_contract: int,
        delegate: Optional[HexAddress] = None,
    ) -> None:
        current_withdrawn_participant = total_withdrawn_participant - pre_withdrawn_participant
        (_, state) = token_network.functions.getChannelInfo(
            channel_identifier, participant, partner
        ).call()
        assert state == ChannelState.OPENED

        (
            deposit,
            withdrawn_amount,
            is_the_closer,
            balance_hash,
            nonce,
            locksroot,
            locked_amount,
        ) = token_network.functions.getChannelParticipantInfo(
            channel_identifier, participant, partner
        ).call()
        assert deposit == deposit_participant
        assert withdrawn_amount == total_withdrawn_participant
        assert is_the_closer is False
        assert balance_hash == fake_bytes(32)
        assert nonce == 0
        assert locksroot == NONEXISTENT_LOCKSROOT
        assert locked_amount == 0

        (
            deposit,
            withdrawn_amount,
            is_the_closer,
            balance_hash,
            nonce,
            locksroot,
            locked_amount,
        ) = token_network.functions.getChannelParticipantInfo(
            channel_identifier, partner, participant
        ).call()
        assert deposit == deposit_partner
        assert withdrawn_amount == total_withdrawn_partner
        assert is_the_closer is False
        assert balance_hash == fake_bytes(32)
        assert nonce == 0
        assert locksroot == NONEXISTENT_LOCKSROOT
        assert locked_amount == 0

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


@pytest.fixture(scope="session")
def create_balance_proof(token_network: Contract, get_private_key: Callable) -> Callable:
    def get(
        channel_identifier: ChannelID,
        participant: HexAddress,
        transferred_amount: TokenAmount = TokenAmount(0),  # noqa
        locked_amount: TokenAmount = TokenAmount(0),  # noqa
        nonce: Nonce = Nonce(0),  # noqa
        locksroot: Optional[Locksroot] = None,
        additional_hash: Optional[AdditionalHash] = None,
        v: int = 27,
        signer: Optional[HexAddress] = None,
        other_token_network: Optional[Contract] = None,
    ) -> OnchainBalanceProof:
        _token_network = other_token_network or token_network
        private_key = get_private_key(signer or participant)
        locksroot = locksroot or LOCKSROOT_OF_NO_LOCKS
        additional_hash = additional_hash or AdditionalHash(b"\x00" * 32)

        balance_hash = hash_balance_data(transferred_amount, locked_amount, locksroot)

        signature = sign_balance_proof(
            private_key,
            _token_network.address,
            _token_network.functions.chain_id().call(),
            channel_identifier,
            MessageTypeId.BALANCE_PROOF,
            balance_hash,
            nonce,
            additional_hash,
            v,
        )
        # The keys of the dictionary correspond to the parameters of
        # create_balance_proof_countersignature.
        return OnchainBalanceProof(
            balance_hash=balance_hash,
            nonce=nonce,
            additional_hash=additional_hash,
            original_signature=signature,
        )

    return get


@pytest.fixture(scope="session")
def create_balance_proof_countersignature(
    token_network: Contract, get_private_key: Callable
) -> Callable:
    def get(
        participant: HexAddress,
        channel_identifier: ChannelID,
        msg_type: MessageTypeId,
        balance_hash: BalanceHash,
        nonce: Nonce,
        additional_hash: AdditionalHash,
        original_signature: Signature,
        v: int = 27,
        other_token_network: Optional[Contract] = None,
    ) -> bytes:
        _token_network = other_token_network or token_network
        private_key = get_private_key(participant)

        non_closing_signature = sign_balance_proof_message(
            private_key,
            _token_network.address,
            _token_network.functions.chain_id().call(),
            channel_identifier,
            msg_type,
            balance_hash,
            nonce,
            additional_hash,
            original_signature,
            v,
        )
        return non_closing_signature

    return get


@pytest.fixture(scope="session")
def create_close_signature_for_no_balance_proof(
    token_network: Contract, get_private_key: Callable
) -> Callable:
    def get(
        participant: HexAddress,
        channel_identifier: ChannelID,
        v: int = 27,
        other_token_network: Optional[Contract] = None,
    ) -> bytes:
        _token_network = other_token_network or token_network
        private_key = get_private_key(participant)

        non_closing_signature = sign_balance_proof_message(
            private_key,
            _token_network.address,
            _token_network.functions.chain_id().call(),
            channel_identifier,
            MessageTypeId.BALANCE_PROOF,
            EMPTY_BALANCE_HASH,
            Nonce(0),
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            v,
        )
        return non_closing_signature

    return get


@pytest.fixture()
def create_withdraw_signatures(token_network: Contract, get_private_key: Callable) -> Callable:
    def get(
        participants_to_sign: Collection[HexAddress],
        channel_identifier: ChannelID,
        participant_who_withdraws: HexAddress,
        amount_to_withdraw: TokenAmount,
        expiration_block: BlockExpiration,
        token_network_address: Optional[HexAddress] = None,
        v: int = 27,
    ) -> List[bytes]:
        if token_network_address is None:
            token_network_address = token_network.address

        signatures = []
        for participant in participants_to_sign:
            private_key = get_private_key(participant)
            signature = sign_withdraw_message(
                private_key,
                token_network_address,
                token_network.functions.chain_id().call(),
                channel_identifier,
                participant_who_withdraws,
                amount_to_withdraw,
                expiration_block,
                v,
            )
            signatures.append(signature)
        return signatures

    return get


def call_settle(
    token_network: Contract,
    channel_identifier: int,
    A: HexAddress,
    vals_A: ChannelValues,
    B: HexAddress,
    vals_B: ChannelValues,
) -> None:
    A_total_transferred = vals_A.transferred + vals_A.locked_amounts.locked
    B_total_transferred = vals_B.transferred + vals_B.locked_amounts.locked
    assert B_total_transferred >= A_total_transferred

    if A_total_transferred != B_total_transferred:
        with pytest.raises(TransactionFailed):
            call_and_transact(
                token_network.functions.settleChannel(
                    channel_identifier=channel_identifier,
                    participant1=B,
                    participant1_transferred_amount=vals_B.transferred,
                    participant1_locked_amount=0,
                    participant1_locksroot=vals_B.locksroot,
                    participant2=A,
                    participant2_transferred_amount=0,
                    participant2_locked_amount=0,
                    participant2_locksroot=vals_A.locksroot,
                ),
                {"from": A},
            )

    contract_function = token_network.functions.settleChannel(
        channel_identifier,
        A,
        vals_A.transferred,
        vals_A.locked_amounts.locked,
        vals_A.locksroot,
        B,
        vals_B.transferred,
        vals_B.locked_amounts.locked,
        vals_B.locksroot,
    )
    # call() raises TransactionFailed exception
    contract_function.call({"from": A})
    # transact() changes the chain state
    call_and_transact(contract_function, {"from": A})
