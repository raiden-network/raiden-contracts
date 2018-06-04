# -*- coding: utf-8 -*-
from raiden_contracts.utils.events import check_address_registered


def test_endpointregistry_calls(endpoint_registry_contract, get_accounts):
    (A, B) = get_accounts(2)
    PORT = '127.0.0.1:38647'
    endpoint_registry_contract.transact({'from': A}).registerEndpoint(PORT)
    assert endpoint_registry_contract.call().findAddressByEndpoint(PORT) == A
    NEW_PORT = '192.168.0.1:4002'
    endpoint_registry_contract.transact({'from': A}).registerEndpoint(NEW_PORT)
    assert endpoint_registry_contract.call().findAddressByEndpoint(NEW_PORT) == A
    assert endpoint_registry_contract.call().findEndpointByAddress(A) == NEW_PORT


def test_events(endpoint_registry_contract, get_accounts, event_handler):
    (A, B) = get_accounts(2)
    ev_handler = event_handler(endpoint_registry_contract)

    PORT = '127.0.0.1:38647'
    txn_hash = endpoint_registry_contract.transact({'from': A}).registerEndpoint(PORT)

    ev_handler.add(txn_hash, 'AddressRegistered', check_address_registered(A, PORT))
    ev_handler.check()
