import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_HUMAN_STANDARD_TOKEN


def test_token_mint(web3, custom_token, get_accounts):
    """ Use the mint() function of the custom token contract """

    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.functions.multiplier().call()
    supply = token.functions.totalSupply().call()

    token_pre_balance = web3.eth.getBalance(token.address)
    tokens_a = 50 * multiplier
    token.functions.mint(tokens_a).call_and_transact({"from": A})
    assert token.functions.balanceOf(A).call() == tokens_a
    assert token.functions.balanceOf(B).call() == 0
    assert token.functions.totalSupply().call() == supply + tokens_a
    assert web3.eth.getBalance(token.address) == token_pre_balance

    tokens_b = 50 * multiplier
    token.functions.mintFor(tokens_b, B).call_and_transact({"from": A})
    assert token.functions.balanceOf(A).call() == tokens_a
    assert token.functions.balanceOf(B).call() == tokens_b
    assert token.functions.totalSupply().call() == supply + tokens_a + tokens_b
    assert web3.eth.getBalance(token.address) == token_pre_balance


def test_approve_transfer(custom_token, get_accounts):
    """ Use the approve() function of the custom token contract """

    (A, B) = get_accounts(2)
    token = custom_token
    token.functions.mint(50).call_and_transact({"from": A})
    initial_balance_A = token.functions.balanceOf(A).call()
    initial_balance_B = token.functions.balanceOf(B).call()
    to_transfer = 20
    token.functions.approve(B, to_transfer).call_and_transact({"from": A})
    token.functions.transferFrom(A, B, to_transfer).call_and_transact({"from": B})
    assert token.functions.balanceOf(B).call() == initial_balance_B + to_transfer
    assert token.functions.balanceOf(A).call() == initial_balance_A - to_transfer

    assert custom_token.functions.allowance(_owner=A, _spender=B).call() == 0
    assert custom_token.functions.approve(_spender=B, _value=25).call_and_transact({"from": A})
    assert custom_token.functions.allowance(_owner=A, _spender=B).call() == 25
    assert custom_token.functions.allowance(_owner=A, _spender=token.address).call() == 0


def test_token_transfer_funds(web3, custom_token, get_accounts):
    """ transferFunds() should fail when the ETH balance of the contract is zero """

    A = get_accounts(1)[0]
    token = custom_token
    multiplier = custom_token.functions.multiplier().call()
    assert multiplier > 0
    supply = token.functions.totalSupply().call()
    assert supply > 0

    owner = custom_token.functions.owner_address().call()

    assert web3.eth.getBalance(token.address) == 0
    with pytest.raises(TransactionFailed):
        token.functions.transferFunds().call({"from": owner})

    token.functions.mint(50).call_and_transact({"from": A})
    assert web3.eth.getBalance(token.address) == 0


def test_custom_token(custom_token, web3, contracts_manager):
    """ See custom_token.address contains the expected code """
    blockchain_bytecode = web3.eth.getCode(custom_token.address).hex()
    compiled_bytecode = contracts_manager.get_runtime_hexcode(CONTRACT_CUSTOM_TOKEN)
    assert blockchain_bytecode == compiled_bytecode


def test_human_standard_token(human_standard_token, web3, contracts_manager):
    """ See human_standard_token.address contains the expected code """
    blockchain_bytecode = web3.eth.getCode(human_standard_token.address).hex()
    compiled_bytecode = contracts_manager.get_runtime_hexcode(CONTRACT_HUMAN_STANDARD_TOKEN)
    assert blockchain_bytecode == compiled_bytecode
