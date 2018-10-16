from raiden_contracts.utils.events import check_address_registered
from raiden_contracts.constants import EVENT_ADDRESS_REGISTERED, CONTRACTS_VERSION


def test_version(endpoint_registry_contract):
    version = endpoint_registry_contract.functions.contract_version().call()
    assert version == CONTRACTS_VERSION


def test_endpointregistry_calls(endpoint_registry_contract, get_accounts):
    (A, B) = get_accounts(2)
    ENDPOINT = '127.0.0.1:38647'
    endpoint_registry_contract.functions.registerEndpoint(ENDPOINT).transact({'from': A})
    NEW_ENDPOINT = '192.168.0.1:4002'
    endpoint_registry_contract.functions.registerEndpoint(NEW_ENDPOINT).transact({'from': A})
    assert endpoint_registry_contract.functions.findEndpointByAddress(
        A,
    ).call() == NEW_ENDPOINT


def test_events(endpoint_registry_contract, get_accounts, event_handler):
    (A, B) = get_accounts(2)
    ev_handler = event_handler(endpoint_registry_contract)

    ENDPOINT = '127.0.0.1:38647'
    txn_hash = endpoint_registry_contract.functions.registerEndpoint(
        ENDPOINT,
    ).transact({'from': A})

    ev_handler.add(txn_hash, EVENT_ADDRESS_REGISTERED, check_address_registered(
        A,
        ENDPOINT,
    ))
    ev_handler.check()
