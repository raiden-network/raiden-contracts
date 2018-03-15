from ethereum import tester
from raiden_contracts.utils.config import C_TOKEN_NETWORK, E_CHANNEL_OPENED


def test_open_channel_call(token_network, get_accounts):
    pass


def test_open_channel_state():
    pass


def test_open_channel_last_index():
    pass


def test_open_channel_fail_existent():
    pass


def test_open_channel_event():
    pass


def test_print_gas_cost(token_network, get_accounts, print_gas):
    (A, B) = get_accounts(2)
    txn_hash = token_network.transact().openChannel(A, B, 7)
    print_gas(txn_hash, 'openChannel')
