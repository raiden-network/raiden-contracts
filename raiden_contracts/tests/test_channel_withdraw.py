import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError
from raiden_contracts.utils.events import check_withdraw
from .fixtures.config import empty_address, fake_bytes
from raiden_contracts.utils.config import (
    E_CHANNEL_WITHDRAW,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED,
    CHANNEL_STATE_OPEN,
    CHANNEL_STATE_CLOSED,
    SETTLE_TIMEOUT_MIN
)
from .utils import MAX_UINT256


def test_withdraw_signature(
        token_network_test,
        create_channel_and_deposit,
        get_accounts,
        create_withdraw_signatures
):
    (A, B) = get_accounts(2)
    deposit_A = 5
    deposit_B = 7
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A, signature_B) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A,
        token_network_test.address
    )

    recovered_address_A = token_network_test.call().recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_A
    )
    assert recovered_address_A == A

    recovered_address_B = token_network_test.call().recoverAddressFromWithdrawMessagePublic(
        channel_identifier,
        A,
        withdraw_A,
        signature_B
    )
    assert recovered_address_B == B


def test_withdraw_call(
        token_network,
        create_channel_and_deposit,
        get_accounts,
        create_withdraw_signatures
):
    (A, B) = get_accounts(2)
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, 10, 1)

    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A
    )

    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).withdraw(
            0x0,
            withdraw_A,
            B,
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).withdraw(
            '',
            withdraw_A,
            B,
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            0x0,
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            '',
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).withdraw(
            A,
            -1,
            B,
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).withdraw(
            A,
            MAX_UINT256 + 1,
            B,
            signature_A_for_A,
            signature_B_for_A
        )

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            empty_address,
            withdraw_A,
            B,
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            empty_address,
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            0,
            B,
            signature_A_for_A,
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            fake_bytes(65),
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A,
            fake_bytes(65)
        )

    token_network.transact({'from': A}).withdraw(
        A,
        withdraw_A,
        B,
        signature_A_for_A,
        signature_B_for_A
    )


def test_withdraw_wrong_state(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel
):
    (A, B) = get_accounts(2)
    withdraw_A = 1

    (_, _, state) = token_network.call().getChannelInfo(A, B)
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED

    with pytest.raises(TransactionFailed):
        withdraw_channel(A, withdraw_A, B)

    create_channel_and_deposit(A, B, 10, 14, SETTLE_TIMEOUT_MIN)
    (_, _, state) = token_network.call().getChannelInfo(A, B)
    assert state == CHANNEL_STATE_OPEN

    # Channel is open, withdraw must work
    withdraw_channel(A, withdraw_A, B)

    token_network.transact({'from': A}).closeChannel(
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64)
    )
    (_, _, state) = token_network.call().getChannelInfo(A, B)
    assert state == CHANNEL_STATE_CLOSED

    with pytest.raises(TransactionFailed):
        withdraw_channel(A, withdraw_A, B)

    web3.testing.mine(SETTLE_TIMEOUT_MIN)
    token_network.transact({'from': A}).settleChannel(
        A,
        0,
        0,
        fake_bytes(32),
        B,
        0,
        0,
        fake_bytes(32)
    )
    (_, _, state) = token_network.call().getChannelInfo(A, B)
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED

    with pytest.raises(TransactionFailed):
        withdraw_channel(A, withdraw_A, B)


def test_withdraw_bigger(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel
):
    (A, B) = get_accounts(2)
    deposit_A = 15
    deposit_B = 13

    create_channel_and_deposit(A, B, deposit_A, deposit_B)

    with pytest.raises(TransactionFailed):
        withdraw_channel(A, deposit_A + deposit_B + 1, B)
    with pytest.raises(TransactionFailed):
        withdraw_channel(B, deposit_A + deposit_B + 1, A)

    withdraw_channel(A, 3, B)
    withdraw_channel(B, 6, A)
    with pytest.raises(TransactionFailed):
        withdraw_channel(A, deposit_A + deposit_B - 5, B)
    with pytest.raises(TransactionFailed):
        withdraw_channel(B, deposit_A + deposit_B - 2, A)

    withdraw_channel(A, deposit_A + deposit_B - 7, B)


def test_withdraw_wrong_signers(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
        create_withdraw_signatures
):
    (A, B, C) = get_accounts(3)
    deposit_A = 15
    deposit_B = 13
    withdraw_A = 5
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A_for_A, signature_B_for_A, signature_C_for_A) = create_withdraw_signatures(
        [A, B, C],
        channel_identifier,
        A,
        withdraw_A
    )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).withdraw(
            A,
            withdraw_A,
            B,
            signature_C_for_A,
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A,
            signature_C_for_A
        )

    token_network.transact({'from': C}).withdraw(
        A,
        withdraw_A,
        B,
        signature_A_for_A,
        signature_B_for_A
    )


def test_withdraw_wrong_signature_content(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
        create_withdraw_signatures
):
    (A, B, C) = get_accounts(3)
    deposit_A = 15
    deposit_B = 13
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    channel_identifier_fake = token_network.call().getChannelIdentifier(A, C)

    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A
    )
    (signature_A_for_A_fake1, signature_B_for_A_fake1) = create_withdraw_signatures(
        [A, B],
        channel_identifier_fake,
        A,
        withdraw_A
    )
    (signature_A_for_A_fake2, signature_B_for_A_fake2) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        B,
        withdraw_A
    )
    (signature_A_for_A_fake3, signature_B_for_A_fake3) = create_withdraw_signatures(
        [A, B],
        channel_identifier,
        A,
        withdraw_A - 1
    )

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A_fake1,
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A,
            signature_B_for_A_fake1
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A_fake2,
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A,
            signature_B_for_A_fake2
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A_fake3,
            signature_B_for_A
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).withdraw(
            A,
            withdraw_A,
            B,
            signature_A_for_A,
            signature_B_for_A_fake3
        )

    token_network.transact({'from': A}).withdraw(
        A,
        withdraw_A,
        B,
        signature_A_for_A,
        signature_B_for_A
    )


def test_withdraw_channel_state(
        get_accounts,
        token_network,
        custom_token,
        create_channel_and_deposit,
        withdraw_channel,
        withdraw_state_tests
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    withdraw_A = 15
    withdraw_B = 2

    create_channel_and_deposit(A, B, deposit_A, deposit_B)

    balance_A = custom_token.call().balanceOf(A)
    balance_B = custom_token.call().balanceOf(B)
    balance_C = custom_token.call().balanceOf(C)
    balance_contract = custom_token.call().balanceOf(token_network.address)

    (_, withdrawn_amount, _, _, _) = token_network.call().getChannelParticipantInfo(A, B)
    assert withdrawn_amount == 0

    withdraw_channel(A, withdraw_A, B, C)

    withdraw_state_tests(
        A,
        deposit_A,
        withdraw_A,
        0,
        balance_A,
        B,
        deposit_B,
        0,
        balance_B,
        balance_contract,
        C, balance_C
    )

    balance_A = custom_token.call().balanceOf(A)
    balance_B = custom_token.call().balanceOf(B)
    balance_C = custom_token.call().balanceOf(C)
    balance_contract = custom_token.call().balanceOf(token_network.address)

    withdraw_channel(B, withdraw_B, A)

    withdraw_state_tests(
        B,
        deposit_B,
        withdraw_B,
        0,
        balance_B,
        A,
        deposit_A,
        withdraw_A,
        balance_A,
        balance_contract
    )

    balance_A = custom_token.call().balanceOf(A)
    balance_B = custom_token.call().balanceOf(B)
    balance_C = custom_token.call().balanceOf(C)
    balance_contract = custom_token.call().balanceOf(token_network.address)

    withdraw_channel(B, withdraw_B + 3, A)

    withdraw_state_tests(
        B,
        deposit_B,
        withdraw_B + 3,
        withdraw_B,
        balance_B,
        A,
        deposit_A,
        withdraw_A,
        balance_A,
        balance_contract
    )


def test_withdraw_event(
        token_network,
        create_channel_and_deposit,
        get_accounts,
        withdraw_channel,
        event_handler
):
    (A, B, C) = get_accounts(3)
    ev_handler = event_handler(token_network)

    channel_identifier = create_channel_and_deposit(A, B, 10, 1)

    txn_hash = withdraw_channel(A, 5, B)
    ev_handler.add(txn_hash, E_CHANNEL_WITHDRAW, check_withdraw(channel_identifier, A, 5))

    txn_hash = withdraw_channel(B, 2, A, C)
    ev_handler.add(txn_hash, E_CHANNEL_WITHDRAW, check_withdraw(channel_identifier, B, 2))

    ev_handler.check()
