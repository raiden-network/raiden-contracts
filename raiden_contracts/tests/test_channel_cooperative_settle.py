import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError

from raiden_contracts.constants import ChannelEvent
from raiden_contracts.tests.utils.constants import EMPTY_ADDRESS
from raiden_contracts.utils.events import check_channel_settled


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_call(
    token_network, create_channel_and_deposit, get_accounts, create_cooperative_settle_signatures
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 5
    balance_B = 25

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, A, balance_A, B, balance_B
    )

    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, -1, B, balance_B, signature_A, signature_B
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, B, -1, signature_A, signature_B
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier, 0x0, balance_A, B, balance_B, signature_A, signature_B
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, 0x0, balance_B, signature_A, signature_B
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, B, balance_B, 0x0, signature_B
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, B, balance_B, signature_A, 0x0
        )

    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier, EMPTY_ADDRESS, balance_A, B, balance_B, signature_A, signature_B
        ).call_and_transact({"from": C})
    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, EMPTY_ADDRESS, balance_B, signature_A, signature_B
        ).call_and_transact({"from": C})

    token_network.functions.cooperativeSettle(
        channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
    ).call_and_transact({"from": C})


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_signatures(
    token_network, create_channel_and_deposit, get_accounts, create_cooperative_settle_signatures
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 4
    balance_B = 26

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A, signature_B, signature_C) = create_cooperative_settle_signatures(
        [A, B, C], channel_identifier, A, balance_A, B, balance_B
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, B, balance_B, signature_C, signature_B
        ).call({"from": C})
    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, B, balance_B, signature_A, signature_C
        ).call({"from": C})
    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_B, B, balance_A, signature_A, signature_B
        ).call({"from": C})

    token_network.functions.cooperativeSettle(
        channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
    ).call_and_transact({"from": C})


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_0(
    custom_token,
    token_network,
    create_channel_and_deposit,
    get_accounts,
    create_cooperative_settle_signatures,
    cooperative_settle_state_tests,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 0
    balance_B = 30

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A, signature_B, _) = create_cooperative_settle_signatures(
        [A, B, C], channel_identifier, A, balance_A, B, balance_B
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.cooperativeSettle(
        channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
    ).call_and_transact({"from": C})

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_00(
    custom_token,
    token_network,
    create_channel_and_deposit,
    get_accounts,
    create_cooperative_settle_signatures,
    cooperative_settle_state_tests,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 0
    deposit_B = 0
    balance_A = 0
    balance_B = 0

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A, signature_B, _) = create_cooperative_settle_signatures(
        [A, B, C], channel_identifier, A, balance_A, B, balance_B
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.cooperativeSettle(
        channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
    ).call_and_transact({"from": C})

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_state(
    custom_token,
    token_network,
    create_channel_and_deposit,
    get_accounts,
    create_cooperative_settle_signatures,
    cooperative_settle_state_tests,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 5
    balance_B = 25
    assert deposit_A + deposit_B == balance_A + balance_B

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, A, balance_A, B, balance_B
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.cooperativeSettle(
        channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
    ).call_and_transact({"from": C})

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_state_withdraw(
    custom_token,
    token_network,
    create_channel_and_deposit,
    withdraw_channel,
    get_accounts,
    create_cooperative_settle_signatures,
    cooperative_settle_state_tests,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    withdraw_A = 3
    withdraw_B = 7
    balance_A = 5
    balance_B = 15
    assert deposit_A + deposit_B == withdraw_A + withdraw_B + balance_A + balance_B

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    withdraw_channel(channel_identifier, A, withdraw_A, B)
    withdraw_channel(channel_identifier, B, withdraw_B, A)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, A, balance_A, B, balance_B
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.cooperativeSettle(
        channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
    ).call_and_transact({"from": C})

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_bigger_withdraw(
    token_network,
    create_channel_and_deposit,
    withdraw_channel,
    get_accounts,
    create_cooperative_settle_signatures,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    withdraw_A = 3
    withdraw_B = 7
    balance_A = 6
    balance_B = 15
    assert deposit_A + deposit_B < withdraw_A + withdraw_B + balance_A + balance_B

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    withdraw_channel(channel_identifier, A, withdraw_A, B)
    withdraw_channel(channel_identifier, B, withdraw_B, A)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, A, balance_A, B, balance_B
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
        ).call({"from": C})


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_wrong_balances(
    token_network, create_channel_and_deposit, get_accounts, create_cooperative_settle_signatures
):
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 7
    balance_B = 23

    balance_A_fail1 = 20
    balance_B_fail1 = 11
    balance_A_fail2 = 6
    balance_B_fail2 = 8

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, A, balance_A, B, balance_B
    )
    (signature_A_fail1, signature_B_fail1) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, A, balance_A_fail1, B, balance_B_fail1
    )
    (signature_A_fail2, signature_B_fail2) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, A, balance_A_fail2, B, balance_B_fail2
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            A,
            balance_A_fail1,
            B,
            balance_B_fail1,
            signature_A_fail1,
            signature_B_fail1,
        ).call({"from": C})
    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            A,
            balance_A_fail2,
            B,
            balance_B_fail2,
            signature_A_fail2,
            signature_B_fail2,
        ).call({"from": C})

    token_network.functions.cooperativeSettle(
        channel_identifier, A, balance_A, B, balance_B, signature_A, signature_B
    ).call_and_transact({"from": C})


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_close_replay_reopened_channel(
    get_accounts,
    token_network,
    create_channel,
    channel_deposit,
    create_cooperative_settle_signatures,
):
    (A, B) = get_accounts(2)
    deposit_A = 15
    deposit_B = 10
    balance_A = 2
    balance_B = 23

    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, A, deposit_A, B)
    channel_deposit(channel_identifier1, B, deposit_B, A)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B], channel_identifier1, B, balance_B, A, balance_A
    )

    token_network.functions.cooperativeSettle(
        channel_identifier1, B, balance_B, A, balance_A, signature_B, signature_A
    ).call_and_transact({"from": B})

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, A, deposit_A, B)
    channel_deposit(channel_identifier2, B, deposit_B, A)

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.cooperativeSettle(
            channel_identifier2, B, balance_B, A, balance_A, signature_B, signature_A
        ).call({"from": B})

    # Signed message with the correct channel identifier must work
    (signature_A2, signature_B2) = create_cooperative_settle_signatures(
        [A, B], channel_identifier2, B, balance_B, A, balance_A
    )
    token_network.functions.cooperativeSettle(
        channel_identifier2, B, balance_B, A, balance_A, signature_B2, signature_A2
    ).call_and_transact({"from": B})


@pytest.mark.skip(reason="Delayed until another milestone")
def test_cooperative_settle_channel_event(
    get_accounts,
    token_network,
    create_channel,
    channel_deposit,
    create_cooperative_settle_signatures,
    event_handler,
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    balance_A = 2
    balance_B = 8
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    (signature_A, signature_B) = create_cooperative_settle_signatures(
        [A, B], channel_identifier, B, balance_B, A, balance_A
    )

    txn_hash = token_network.functions.cooperativeSettle(
        channel_identifier, B, balance_B, A, balance_A, signature_B, signature_A
    ).call_and_transact({"from": B})

    ev_handler.add(
        txn_hash,
        ChannelEvent.SETTLED,
        check_channel_settled(channel_identifier, balance_B, balance_A),
    )
    ev_handler.check()
