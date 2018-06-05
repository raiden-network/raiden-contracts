import pytest
from eth_tester.exceptions import TransactionFailed
from eth_utils import denoms
from web3.exceptions import ValidationError


def test_token_mint(web3, custom_token, get_accounts):
    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.functions.multiplier().call()
    supply = token.functions.totalSupply().call()

    token_pre_balance = web3.eth.getBalance(token.address)

    with pytest.raises(ValidationError):
        token.functions.mint(3).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token.functions.mint().transact({'from': A})

    wei_value = 10**17 + 21000
    tokens = 50 * multiplier
    token.functions.mint().transact({'from': A, 'value': wei_value})
    assert token.functions.balanceOf(A).call() == tokens
    assert token.functions.totalSupply().call() == supply + tokens
    assert web3.eth.getBalance(token.address) == token_pre_balance + wei_value


def test_approve_transfer(web3, custom_token, get_accounts):
    (A, B) = get_accounts(2)
    token = custom_token
    token.functions.mint().transact({'from': A, 'value': 100 * denoms.finney})
    initial_balance_A = token.functions.balanceOf(A).call()
    initial_balance_B = token.functions.balanceOf(B).call()
    to_transfer = 20
    token.functions.approve(B, to_transfer).transact({'from': A})
    token.functions.transferFrom(A, B, to_transfer).transact({'from': B})
    assert token.functions.balanceOf(B).call() == initial_balance_B + to_transfer
    assert token.functions.balanceOf(A).call() == initial_balance_A - to_transfer


def test_token_transfer_funds(web3, custom_token, get_accounts, txn_gas):
    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.functions.multiplier().call()
    assert multiplier > 0
    supply = token.functions.totalSupply().call()
    assert supply > 0
    wei_value = 10**17 + 21000

    owner = custom_token.functions.owner_address().call()

    with pytest.raises(TransactionFailed):
        token.functions.transferFunds().transact({'from': owner})

    token.functions.mint().transact({'from': A, 'value': wei_value})

    owner_prebalance = web3.eth.getBalance(owner)

    tx_hash = token.functions.transferFunds().transact({'from': owner})

    assert web3.eth.getBalance(owner) == owner_prebalance + wei_value - txn_gas(tx_hash)
    assert web3.eth.getBalance(token.address) == 0
