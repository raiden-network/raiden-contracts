import pytest
from ethereum import tester
from tests.fixtures.token import *


def test_token_mint(web3, custom_token, get_accounts):
    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.call().multiplier()
    supply = token.call().totalSupply()

    token_pre_balance = web3.eth.getBalance(token.address)

    with pytest.raises(TypeError):
        token.transact({'from': A}).mint(3)

    with pytest.raises(tester.TransactionFailed):
        token.transact({'from': A}).mint()

    wei_value = 10**17 + 21000
    tokens = 50 * multiplier;
    token.transact({'from': A, 'value': wei_value}).mint()
    assert token.call().balanceOf(A) == tokens
    assert token.call().totalSupply() == supply + tokens
    assert web3.eth.getBalance(token.address) == token_pre_balance + wei_value


def test_token_transfer_funds(web3, owner, custom_token, get_accounts, txn_gas):
    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.call().multiplier()
    supply = token.call().totalSupply()
    wei_value = 10**17 + 21000

    with pytest.raises(tester.TransactionFailed):
        token.transact({'from': owner}).transferFunds()

    token.transact({'from': A, 'value': wei_value}).mint()

    owner_prebalance = web3.eth.getBalance(owner)

    tx_hash = token.transact({'from': owner}).transferFunds()

    assert web3.eth.getBalance(owner) == owner_prebalance + wei_value - txn_gas(tx_hash)
    assert web3.eth.getBalance(token.address) == 0
