from raiden_contracts.constants import CONTRACTS_VERSION, EVENT_ADDRESS_REGISTERED
from raiden_contracts.utils.events import check_address_registered


def test_version(endpoint_registry_contract):
    """ EndpointRegistry has the right contracts version """
    version = endpoint_registry_contract.functions.contract_version().call()
    assert version == CONTRACTS_VERSION


def test_endpointregistry_calls(endpoint_registry_contract, get_accounts):
    """ Overwrite an endpoint registration """
    A = get_accounts(1)[0]
    ENDPOINT = "127.0.0.1:38647"
    endpoint_registry_contract.functions.registerEndpoint(ENDPOINT).call_and_transact({"from": A})
    NEW_ENDPOINT = "192.168.0.1:4002"
    endpoint_registry_contract.functions.registerEndpoint(NEW_ENDPOINT).call_and_transact(
        {"from": A}
    )
    assert endpoint_registry_contract.functions.findEndpointByAddress(A).call() == NEW_ENDPOINT


def test_events(endpoint_registry_contract, get_accounts, event_handler):
    """ An endpoint registration causes an EVENT_ADDRESS_REGISTERED event """
    A = get_accounts(1)[0]
    ev_handler = event_handler(endpoint_registry_contract)

    ENDPOINT = "127.0.0.1:38647"
    txn_hash = endpoint_registry_contract.functions.registerEndpoint(ENDPOINT).call_and_transact(
        {"from": A}
    )

    ev_handler.add(txn_hash, EVENT_ADDRESS_REGISTERED, check_address_registered(A, ENDPOINT))
    ev_handler.check()
