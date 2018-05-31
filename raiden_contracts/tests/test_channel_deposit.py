import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError
from raiden_contracts.utils.config import E_CHANNEL_NEW_DEPOSIT
from raiden_contracts.utils.events import check_new_deposit
from .fixtures.config import empty_address, fake_address
from eth_utils import denoms


def test_deposit_channel_call(token_network, custom_token, create_channel, get_accounts):
    (A, B) = get_accounts(2)
    create_channel(A, B)[0]

    custom_token.transact({'from': A, 'value': 100 * denoms.finney}).mint()
    deposit_A = custom_token.call().balanceOf(A)

    custom_token.transact({'from': A}).approve(token_network.address, deposit_A)

    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            -1,
            A,
            deposit_A
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            '',
            deposit_A,
            B
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            fake_address,
            deposit_A,
            B
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            0x0,
            deposit_A,
            B
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            A,
            deposit_A,
            ''
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            A,
            deposit_A,
            fake_address
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            A,
            deposit_A,
            0x0
        )
    with pytest.raises(ValidationError):
        token_network.transact({'from': A}).setTotalDeposit(
            A,
            -1,
            B
        )

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).setTotalDeposit(
            empty_address,
            deposit_A,
            B
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).setTotalDeposit(
            A,
            deposit_A,
            empty_address
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).setTotalDeposit(
            A,
            0,
            B
        )

    token_network.transact({'from': A}).setTotalDeposit(
        A,
        deposit_A,
        B
    )


def test_deposit_notapproved(
        token_network,
        custom_token,
        create_channel,
        get_accounts
):
    (A, B) = get_accounts(2)
    create_channel(A, B)
    deposit_A = 1

    custom_token.transact({'from': A, 'value': 100 * denoms.finney}).mint()
    balance = custom_token.call().balanceOf(A)
    assert balance >= deposit_A

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).setTotalDeposit(A, deposit_A, B)


def test_small_deposit_fail(
        token_network,
        create_channel,
        channel_deposit,
        assign_tokens,
        get_accounts
):
    (A, B) = get_accounts(2)
    create_channel(A, B)
    channel_deposit(A, 2, B)

    assign_tokens(A, 1)

    # setTotalDeposit is idempotent
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': A}).setTotalDeposit(A, 1, B)


def test_deposit_delegate(token_network, get_accounts, create_channel, channel_deposit):
    (A, B, C) = get_accounts(3)
    create_channel(A, B)
    channel_deposit(A, 2, B, tx_from=C)


def test_deposit_channel_state(token_network, create_channel, channel_deposit, get_accounts):
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    create_channel(A, B)

    A_deposit = token_network.call().getChannelParticipantInfo(A, B)[0]
    assert A_deposit == 0

    B_deposit = token_network.call().getChannelParticipantInfo(B, A)[0]
    assert B_deposit == 0

    channel_deposit(A, deposit_A, B)
    A_deposit = token_network.call().getChannelParticipantInfo(A, B)[0]
    assert A_deposit == deposit_A

    channel_deposit(B, deposit_B, A)
    B_deposit = token_network.call().getChannelParticipantInfo(B, A)[0]
    assert B_deposit == deposit_B


def test_deposit_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    channel_identifier = create_channel(A, B)[0]

    txn_hash = channel_deposit(A, deposit_A, B)

    ev_handler.add(
        txn_hash,
        E_CHANNEL_NEW_DEPOSIT,
        check_new_deposit(channel_identifier, A, deposit_A)
    )

    txn_hash = channel_deposit(B, deposit_B, A)
    ev_handler.add(
        txn_hash,
        E_CHANNEL_NEW_DEPOSIT,
        check_new_deposit(channel_identifier, B, deposit_B)
    )

    ev_handler.check()
