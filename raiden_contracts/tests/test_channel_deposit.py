import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError
from raiden_contracts.constants import EVENT_CHANNEL_DEPOSIT, MAX_TOKENS_DEPLOY
from raiden_contracts.utils.events import check_new_deposit
from .fixtures.config import empty_address, fake_address
from raiden_contracts.tests.utils import MAX_UINT256


def test_deposit_channel_call(token_network, custom_token, create_channel, get_accounts):
    (A, B) = get_accounts(2)
    deposit_A = 200
    create_channel(A, B)[0]

    custom_token.functions.mint(deposit_A).transact({'from': A})

    custom_token.functions.approve(token_network.address, deposit_A).transact({'from': A})

    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            -1,
            A,
            deposit_A,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            '',
            deposit_A,
            B,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            fake_address,
            deposit_A,
            B,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            0x0,
            deposit_A,
            B,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            A,
            deposit_A,
            '',
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            A,
            deposit_A,
            fake_address,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            A,
            deposit_A,
            0x0,
        ).transact({'from': A})
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(
            A,
            -1,
            B,
        ).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            empty_address,
            deposit_A,
            B,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            A,
            deposit_A,
            empty_address,
        ).transact({'from': A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(
            A,
            0,
            B,
        ).transact({'from': A})

    token_network.functions.setTotalDeposit(
        A,
        deposit_A,
        B,
    ).transact({'from': A})


def test_deposit_notapproved(
        token_network,
        custom_token,
        create_channel,
        get_accounts,
):
    (A, B) = get_accounts(2)
    create_channel(A, B)
    deposit_A = 1

    custom_token.functions.mint(deposit_A).transact({'from': A})
    balance = custom_token.functions.balanceOf(A).call()
    assert balance >= deposit_A

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(A, deposit_A, B).transact({'from': A})


def test_small_deposit_fail(
        token_network,
        create_channel,
        channel_deposit,
        assign_tokens,
        get_accounts,
):
    (A, B) = get_accounts(2)
    create_channel(A, B)
    channel_deposit(A, 2, B)

    assign_tokens(A, 1)

    # setTotalDeposit is idempotent
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalDeposit(A, 1, B).transact({'from': A})


def test_deposit_delegate(token_network, get_accounts, create_channel, channel_deposit):
    (A, B, C) = get_accounts(3)
    create_channel(A, B)
    channel_deposit(A, 2, B, tx_from=C)


@pytest.mark.skip('Not necessary with limited deposits fo the test release.')
def test_channel_deposit_overflow(token_network, get_accounts, create_channel, channel_deposit):
    (A, B) = get_accounts(2)
    deposit_A = 50
    deposit_B_ok = MAX_UINT256 - deposit_A
    deposit_B_fail = deposit_B_ok + 1

    create_channel(A, B)
    channel_deposit(A, deposit_A, B)

    with pytest.raises(TransactionFailed):
        channel_deposit(B, deposit_B_fail, A)

    channel_deposit(B, deposit_B_ok, A)


def test_channel_deposit_limit(token_network, get_accounts, create_channel, channel_deposit):
    (A, B) = get_accounts(2)
    deposit_B_ok = MAX_TOKENS_DEPLOY * (10 ** 18)
    deposit_B_fail = deposit_B_ok + 1

    create_channel(A, B)

    channel_deposit(B, deposit_B_ok, A)

    with pytest.raises(TransactionFailed):
        channel_deposit(B, deposit_B_fail, A)


def test_deposit_channel_state(token_network, create_channel, channel_deposit, get_accounts):
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    create_channel(A, B)

    A_deposit = token_network.functions.getChannelParticipantInfo(A, B).call()[0]
    assert A_deposit == 0

    B_deposit = token_network.functions.getChannelParticipantInfo(B, A).call()[0]
    assert B_deposit == 0

    channel_deposit(A, deposit_A, B)
    A_deposit = token_network.functions.getChannelParticipantInfo(A, B).call()[0]
    assert A_deposit == deposit_A

    channel_deposit(B, deposit_B, A)
    B_deposit = token_network.functions.getChannelParticipantInfo(B, A).call()[0]
    assert B_deposit == deposit_B


def test_deposit_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        event_handler,
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    channel_identifier = create_channel(A, B)[0]

    txn_hash = channel_deposit(A, deposit_A, B)

    ev_handler.add(
        txn_hash,
        EVENT_CHANNEL_DEPOSIT,
        check_new_deposit(channel_identifier, A, deposit_A),
    )

    txn_hash = channel_deposit(B, deposit_B, A)
    ev_handler.add(
        txn_hash,
        EVENT_CHANNEL_DEPOSIT,
        check_new_deposit(channel_identifier, B, deposit_B),
    )

    ev_handler.check()
