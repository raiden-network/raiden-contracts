import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.utils.config import (
    E_CHANNEL_SETTLED,
    SETTLE_TIMEOUT_MIN
)
from raiden_contracts.utils.events import check_channel_settled
from raiden_contracts.tests.fixtures.channel_test_values import channel_settle_test_values
from .utils import get_settlement_amounts
from .fixtures.config import fake_hex, fake_bytes


def test_settle_no_bp_success(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        create_balance_proof
):
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 6
    settle_timeout = SETTLE_TIMEOUT_MIN
    locksroot = fake_bytes(32)
    additional_hash = fake_bytes(32)
    create_channel_and_deposit(A, B, deposit_A, deposit_B)

    # Close channel with no balance proof
    token_network.functions.closeChannel(
        B,
        locksroot,
        0,
        additional_hash,
        fake_bytes(64)
    ).transact({'from': A})

    # Do not call updateNonClosingBalanceProof

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    # Settling the channel should work with no balance proofs
    token_network.functions.settleChannel(
        A,
        0,
        0,
        locksroot,
        B,
        0,
        0,
        locksroot
    ).transact({'from': A})


@pytest.mark.parametrize('channel_test_values', channel_settle_test_values)
def test_settle_channel_state(
        web3,
        get_accounts,
        custom_token,
        token_network,
        create_channel_and_deposit,
        withdraw_channel,
        close_and_update_channel,
        settle_state_tests,
        channel_test_values
):
    (A, B) = get_accounts(2)
    (vals_A, vals_B) = channel_test_values
    locksroot_A = fake_bytes(32, '02')
    locksroot_B = fake_bytes(32, '03')
    create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

    withdraw_channel(A, vals_A.withdrawn, B)
    withdraw_channel(B, vals_B.withdrawn, A)

    close_and_update_channel(
        A,
        vals_A.transferred,
        vals_A.locked,
        locksroot_A,
        B,
        vals_B.transferred,
        vals_B.locked,
        locksroot_B
    )

    web3.testing.mine(SETTLE_TIMEOUT_MIN)

    # Calling settle with the wrong participant order must fail
    with pytest.raises(TransactionFailed):
        token_network.functions.settleChannel(
            B,
            vals_B.transferred,
            vals_B.locked,
            locksroot_B,
            A,
            vals_A.transferred,
            vals_A.locked,
            locksroot_A
        ).transact({'from': A})

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    token_network.functions.settleChannel(
        A,
        vals_A.transferred,
        vals_A.locked,
        locksroot_A,
        B,
        vals_B.transferred,
        vals_B.locked,
        locksroot_B
    ).transact({'from': A})

    # Calculate how much A and B should receive
    (A_amount, B_amount, locked_amount) = get_settlement_amounts(vals_A, vals_B)

    settle_state_tests(
        A,
        A_amount,
        locksroot_A,
        vals_A.locked,
        B,
        B_amount,
        locksroot_B,
        vals_B.locked,
        pre_balance_A,
        pre_balance_B,
        pre_balance_contract
    )


def test_settle_channel_event(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    settle_timeout = SETTLE_TIMEOUT_MIN
    locksroot = fake_hex(32, '00')

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, deposit_A, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 1, locksroot)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, locksroot)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    token_network.functions.closeChannel(B, *balance_proof_B).transact({'from': A})
    token_network.functions.updateNonClosingBalanceProof(
        A, B,
        *balance_proof_A,
        balance_proof_update_signature_B
    ).transact({'from': B})

    web3.testing.mine(settle_timeout)
    txn_hash = token_network.functions.settleChannel(
        A,
        10,
        0,
        locksroot,
        B,
        5,
        0,
        locksroot
    ).transact({'from': A})

    ev_handler.add(txn_hash, E_CHANNEL_SETTLED, check_channel_settled(
        channel_identifier,
        5,
        5
    ))
    ev_handler.check()
