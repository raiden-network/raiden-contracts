# -*- coding: utf-8 -*-
from raiden_contracts.utils.events import check_address_registered
from raiden_contracts.constants import EVENT_ADDRESS_REGISTERED


def test_endpointregistry_calls(endpoint_registry_contract, get_accounts):
    (A, B) = get_accounts(2)
    PORT = '127.0.0.1:38647'
    endpoint_registry_contract.functions.registerEndpoint(PORT).transact({'from': A})
    assert endpoint_registry_contract.functions.findAddressByEndpoint(PORT).call() == A
    NEW_PORT = '192.168.0.1:4002'
    endpoint_registry_contract.functions.registerEndpoint(NEW_PORT).transact({'from': A})
    assert endpoint_registry_contract.functions.findAddressByEndpoint(NEW_PORT).call() == A
    assert endpoint_registry_contract.functions.findEndpointByAddress(A).call() == NEW_PORT


def test_events(endpoint_registry_contract, get_accounts, event_handler):
    (A, B) = get_accounts(2)
    ev_handler = event_handler(endpoint_registry_contract)

    PORT = '127.0.0.1:38647'
    txn_hash = endpoint_registry_contract.functions.registerEndpoint(PORT).transact({'from': A})

    ev_handler.add(txn_hash, EVENT_ADDRESS_REGISTERED, check_address_registered(A, PORT))
    ev_handler.check()
