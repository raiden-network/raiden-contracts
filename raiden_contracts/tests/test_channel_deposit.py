import pytest
from ethereum import tester
from raiden_contracts.utils.config import E_CHANNEL_NEW_DEPOSIT
from raiden_contracts.utils.events import check_new_deposit
from .fixtures.config import (
    empty_address,
    fake_address,
)


def test_deposit_channel_call(token_network, custom_token, create_channel, get_accounts):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)

    custom_token.transact({'from': A, 'value': 10 ** 18}).mint()
    deposit_A = custom_token.call().balanceOf(A)

    custom_token.transact({'from': A}).approve(token_network.address, deposit_A)

    with pytest.raises(TypeError):
        token_network.transact({'from': A}).setDeposit(
            -1,
            A,
            deposit_A
        )
    with pytest.raises(TypeError):
        token_network.transact({'from': A}).setDeposit(
            channel_identifier,
            '',
            deposit_A
        )
    with pytest.raises(TypeError):
        token_network.transact({'from': A}).setDeposit(
            channel_identifier,
            fake_address,
            deposit_A
        )
    with pytest.raises(TypeError):
        token_network.transact({'from': A}).setDeposit(
            channel_identifier,
            0x0,
            deposit_A
        )
    with pytest.raises(TypeError):
        token_network.transact({'from': A}).setDeposit(
            channel_identifier,
            A,
            -1
        )

    with pytest.raises(tester.TransactionFailed):
        token_network.transact({'from': A}).setDeposit(
            2,
            A,
            deposit_A
        )
    with pytest.raises(tester.TransactionFailed):
        token_network.transact({'from': A}).setDeposit(
            channel_identifier,
            empty_address,
            deposit_A
        )
    with pytest.raises(tester.TransactionFailed):
        token_network.transact({'from': A}).setDeposit(
            channel_identifier,
            A,
            0
        )

    token_network.transact({'from': A}).setDeposit(
        channel_identifier,
        A,
        deposit_A
    )


def test_deposit_channel_state(token_network, create_channel, channel_deposit, get_accounts):
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    channel_identifier = create_channel(A, B)

    A_state = token_network.call().getChannelParticipantInfo(1, A, B)
    assert A_state[0] == 0

    B_state = token_network.call().getChannelParticipantInfo(1, B, A)
    assert B_state[0] == 0

    channel_deposit(channel_identifier, A, deposit_A)
    A_state = token_network.call().getChannelParticipantInfo(1, A, B)
    assert A_state[0] == deposit_A

    channel_deposit(channel_identifier, B, deposit_B)
    B_state = token_network.call().getChannelParticipantInfo(1, B, A)
    assert B_state[0] == deposit_B


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

    channel_identifier = create_channel(A, B)

    txn_hash = channel_deposit(channel_identifier, A, deposit_A)
    ev_handler.add(
        txn_hash,
        E_CHANNEL_NEW_DEPOSIT,
        check_new_deposit(channel_identifier, A, deposit_A)
    )

    txn_hash = channel_deposit(channel_identifier, B, deposit_B)
    ev_handler.add(
        txn_hash,
        E_CHANNEL_NEW_DEPOSIT,
        check_new_deposit(channel_identifier, B, deposit_B)
    )

    ev_handler.check()
