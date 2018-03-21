from raiden_contracts.utils.config import E_CHANNEL_NEW_DEPOSIT
from .utils import check_new_deposit


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
