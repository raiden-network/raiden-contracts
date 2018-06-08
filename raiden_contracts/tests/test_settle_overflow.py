from collections import namedtuple
from raiden_contracts.utils.config import SETTLE_TIMEOUT_MIN
from .utils import get_settlement_amounts
from .fixtures.config import fake_bytes


def test_settle_overflow(
        web3,
        get_accounts,
        custom_token,
        token_network,
        create_channel_and_deposit,
        close_and_update_channel,
        settle_state_tests,
):

    ChannelValues = namedtuple('ChannelValues', [
        'deposit',
        'withdrawn',
        'transferred',
        'locked'
    ])
    """
    Closer can currently construct a transferred amount that will cause the amout computation in
    getSettleTransferAmounts function to overflow
    """
    participant_2_gets_all = (
        ChannelValues(deposit=666, withdrawn=0, transferred=0, locked=0),
        ChannelValues(deposit=1, withdrawn=0, transferred=2**256 - 666, locked=0)
    )

    (A, B) = get_accounts(2)
    vals_A, vals_B = participant_2_gets_all
    locksroot_A = fake_bytes(32, '02')
    locksroot_B = fake_bytes(32, '03')
    create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)

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

    (A_amount_expected, B_amount_expected, locked_amount) = get_settlement_amounts(vals_A, vals_B)
    A_amount_real = custom_token.functions.balanceOf(A).call() - pre_balance_A
    B_amount_real = custom_token.functions.balanceOf(B).call() - pre_balance_B
    assert A_amount_expected is not A_amount_real
    assert B_amount_expected is not B_amount_real

    settle_state_tests(
        A,
        A_amount_real,
        locksroot_A,
        vals_A.locked,
        B,
        B_amount_real,
        locksroot_B,
        vals_B.locked,
        pre_balance_A,
        pre_balance_B,
        pre_balance_contract
    )
