from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_HUMAN_STANDARD_TOKEN
from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.utils import call_and_transact


def test_token_mint(web3: Web3, custom_token: Contract, get_accounts: Callable) -> None:
    """Use the mint() function of the custom token contract"""

    (A, B) = get_accounts(2)
    token = custom_token
    multiplier = custom_token.functions.multiplier().call()
    supply = token.functions.totalSupply().call()

    token_pre_balance = web3.eth.get_balance(token.address)
    tokens_a = 50 * multiplier
    call_and_transact(token.functions.mint(tokens_a), {"from": A})
    assert token.functions.balanceOf(A).call() == tokens_a
    assert token.functions.balanceOf(B).call() == 0
    assert token.functions.totalSupply().call() == supply + tokens_a
    assert web3.eth.get_balance(token.address) == token_pre_balance

    tokens_b = 50 * multiplier
    call_and_transact(token.functions.mintFor(tokens_b, B), {"from": A})
    assert token.functions.balanceOf(A).call() == tokens_a
    assert token.functions.balanceOf(B).call() == tokens_b
    assert token.functions.totalSupply().call() == supply + tokens_a + tokens_b
    assert web3.eth.get_balance(token.address) == token_pre_balance


def test_approve_transfer(custom_token: Contract, get_accounts: Callable) -> None:
    """Use the approve() function of the custom token contract"""

    (A, B) = get_accounts(2)
    token = custom_token
    call_and_transact(token.functions.mint(50), {"from": A})
    initial_balance_A = token.functions.balanceOf(A).call()
    initial_balance_B = token.functions.balanceOf(B).call()
    to_transfer = 20
    call_and_transact(token.functions.approve(B, to_transfer), {"from": A})
    call_and_transact(token.functions.transferFrom(A, B, to_transfer), {"from": B})
    assert token.functions.balanceOf(B).call() == initial_balance_B + to_transfer
    assert token.functions.balanceOf(A).call() == initial_balance_A - to_transfer

    assert custom_token.functions.allowance(_owner=A, _spender=B).call() == 0
    assert call_and_transact(custom_token.functions.approve(_spender=B, _value=25), {"from": A})
    assert custom_token.functions.allowance(_owner=A, _spender=B).call() == 25
    assert custom_token.functions.allowance(_owner=A, _spender=token.address).call() == 0


def test_token_transfer_funds(web3: Web3, custom_token: Contract, get_accounts: Callable) -> None:
    """transferFunds() should fail when the ETH balance of the contract is zero"""

    A = get_accounts(1)[0]
    token = custom_token
    multiplier = custom_token.functions.multiplier().call()
    assert multiplier > 0
    supply = token.functions.totalSupply().call()
    assert supply > 0

    owner = custom_token.functions.owner_address().call()

    assert web3.eth.get_balance(token.address) == 0
    with pytest.raises(TransactionFailed):
        token.functions.transferFunds().call({"from": owner})

    call_and_transact(token.functions.mint(50), {"from": A})
    assert web3.eth.get_balance(token.address) == 0


def test_custom_token(
    custom_token: Contract, web3: Web3, contracts_manager: ContractManager
) -> None:
    """See custom_token.address contains the expected code"""
    blockchain_bytecode = web3.eth.get_code(custom_token.address)
    compiled_bytecode = contracts_manager.get_runtime_hexcode(CONTRACT_CUSTOM_TOKEN)
    assert blockchain_bytecode.hex() == compiled_bytecode


def test_human_standard_token(
    human_standard_token: Contract, web3: Web3, contracts_manager: ContractManager
) -> None:
    """See human_standard_token.address contains the expected code"""
    blockchain_bytecode = web3.eth.get_code(human_standard_token.address)
    compiled_bytecode = contracts_manager.get_runtime_hexcode(CONTRACT_HUMAN_STANDARD_TOKEN)
    assert blockchain_bytecode.hex() == compiled_bytecode
