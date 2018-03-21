from raiden_contracts.utils.config import E_TRANSFER_UPDATED
from .utils import check_transfer_updated


# TODO: test transferred_amount > deposit - this works now!!!!
def test_update_channel_fail_small_deposit():
    pass


def test_update_channel_event_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)
    balance_proof_A = create_balance_proof(channel_identifier, B, 0, 0)
    balance_proof_B = create_balance_proof(channel_identifier, A, 0, 0)

    token_network.transact({'from': A}).closeChannel(*balance_proof_A)
    txn_hash = token_network.transact({'from': B}).updateTransfer(*balance_proof_B)

    ev_handler.add(txn_hash, E_TRANSFER_UPDATED, check_transfer_updated(channel_identifier, A))
    ev_handler.check()


def test_update_channel_event(
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
    deposit_B = 10

    channel_identifier = create_channel(A, B)
    channel_deposit(channel_identifier, A, deposit_A)
    channel_deposit(channel_identifier, B, deposit_B)
    balance_proof_A = create_balance_proof(channel_identifier, B, 5, 3)
    balance_proof_B = create_balance_proof(channel_identifier, A, 2, 1)

    token_network.transact({'from': A}).closeChannel(*balance_proof_A)
    txn_hash = token_network.transact({'from': B}).updateTransfer(*balance_proof_B)

    ev_handler.add(txn_hash, E_TRANSFER_UPDATED, check_transfer_updated(channel_identifier, A))
    ev_handler.check()
