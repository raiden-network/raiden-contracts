from raiden_contracts.utils.config import E_CHANNEL_CLOSED
from .utils import check_channel_closed


# TODO: test transferred_amount > deposit - this works now!!!!
def test_close_channel_fail_small_deposit():
    pass


# TODO: test event argument when a delegate closes
def test_close_channel_event_delegate():
    pass


def test_close_channel_event_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)
    balance_proof = create_balance_proof(channel_identifier, B, 0, 0)

    txn_hash = token_network.transact({'from': A}).closeChannel(*balance_proof)

    ev_handler.add(txn_hash, E_CHANNEL_CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()


def test_close_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10

    channel_identifier = create_channel(A, B)
    channel_deposit(channel_identifier, A, deposit_A)
    balance_proof = create_balance_proof(channel_identifier, B, 5, 3)

    txn_hash = token_network.transact({'from': A}).closeChannel(*balance_proof)

    ev_handler.add(txn_hash, E_CHANNEL_CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()
