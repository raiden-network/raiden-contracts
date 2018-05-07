import pytest
from eth_tester.exceptions import TransactionFailed
from eth_utils import denoms
from web3.exceptions import ValidationError


def test_token_mint(web3, custom_token, get_accounts):
    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.call().multiplier()
    supply = token.call().totalSupply()

    token_pre_balance = web3.eth.getBalance(token.address)

    with pytest.raises(ValidationError):
        token.transact({'from': A}).mint(3)

    with pytest.raises(TransactionFailed):
        token.transact({'from': A}).mint()

    wei_value = 10**17 + 21000
    tokens = 50 * multiplier
    token.transact({'from': A, 'value': wei_value}).mint()
    assert token.call().balanceOf(A) == tokens
    assert token.call().totalSupply() == supply + tokens
    assert web3.eth.getBalance(token.address) == token_pre_balance + wei_value


def test_approve_transfer(web3, custom_token, get_accounts):
    (A, B) = get_accounts(2)
    token = custom_token
    token.transact({'from': A, 'value': 100 * denoms.finney}).mint()
    initial_balance_A = token.call().balanceOf(A)
    initial_balance_B = token.call().balanceOf(B)
    to_transfer = 20
    token.transact({'from': A}).approve(B, to_transfer)
    token.transact({'from': B}).transferFrom(A, B, to_transfer)
    assert token.call().balanceOf(B) == initial_balance_B + to_transfer
    assert token.call().balanceOf(A) == initial_balance_A - to_transfer


def test_token_transfer_funds(web3, custom_token, get_accounts, txn_gas):
    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.call().multiplier()
    assert multiplier > 0
    supply = token.call().totalSupply()
    assert supply > 0
    wei_value = 10**17 + 21000

    owner = custom_token.functions.owner_address().call()

    with pytest.raises(TransactionFailed):
        token.transact({'from': owner}).transferFunds()

    token.transact({'from': A, 'value': wei_value}).mint()

    owner_prebalance = web3.eth.getBalance(owner)

    tx_hash = token.transact({'from': owner}).transferFunds()

    assert web3.eth.getBalance(owner) == owner_prebalance + wei_value - txn_gas(tx_hash)
    assert web3.eth.getBalance(token.address) == 0
