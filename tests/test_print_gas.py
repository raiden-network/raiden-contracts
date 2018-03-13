import pytest
from ethereum import tester
from utils.config import *
from utils.sign import *
from tests.fixtures import *


def test_token_network_registry(chain, token_network_registry, custom_token, print_gas):
    TokenNetworkRegistry = chain.provider.get_contract_factory(C_TOKEN_NETWORK_REGISTRY)
    deploy_txn_hash = TokenNetworkRegistry.deploy(args=[custom_token.address])
    print_gas(deploy_txn_hash, C_TOKEN_NETWORK_REGISTRY + ' DEPLOYMENT')

    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)
    print_gas(txn_hash, C_TOKEN_NETWORK_REGISTRY + '.createERC20TokenNetwork')


def test_token_network_deployment(chain, print_gas, custom_token, secret_registry):
    TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
    deploy_txn_hash = TokenNetwork.deploy(args=[
        custom_token.address,
        secret_registry.address
    ])

    print_gas(deploy_txn_hash, C_TOKEN_NETWORK + ' DEPLOYMENT')


def test_secret_registry(secret_registry, print_gas):
    secret = b'secretsecretsecretsecretsecretse'
    txn_hash = secret_registry.transact().registerSecret(secret)
    print_gas(txn_hash, C_SECRET_REGISTRY + '.registerSecret')


def test_channel_deposit(web3, token_network, custom_token, get_accounts, print_gas):
    (A, B) = get_accounts(2)

    custom_token.transact({'from': A, 'value': 10 ** 18}).mint()
    custom_token.transact({'from': B, 'value': 10 ** 18}).mint()
    assert custom_token.call().balanceOf(A) == 50 * custom_token.call().multiplier()
    assert custom_token.call().balanceOf(B) == 50 * custom_token.call().multiplier()

    custom_token.transact({'from': A}).approve(token_network.address, 50)
    custom_token.transact({'from': B}).approve(token_network.address, 50)

    txn_hash = token_network.transact().openChannel(A, B, 7)
    print_gas(txn_hash, C_TOKEN_NETWORK + '.openChannel')

    txn_hash = token_network.transact({'from': A}).setDeposit(1, A, 20)
    txn_hash = token_network.transact({'from': B}).setDeposit(1, B, 10)
    print_gas(txn_hash, C_TOKEN_NETWORK + '.setDeposit')

    nonce = 3
    transferred_amount = 5
    locksroot = b'\x00' * 32
    additional_hash = b'\x00' * 32
    signature = sign_balance_proof(
        tester.k3,
        1,
        token_network.address,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash,
    )
    # TODO: compare transferred_amount with deposit!!!!
    txn_hash = token_network.transact({'from': A}).closeChannel(
        1,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash,
        signature
    )
    print_gas(txn_hash, C_TOKEN_NETWORK + '.closeChannel')

    nonce = 3
    transferred_amount = 15
    locksroot = b'\x00' * 32
    additional_hash = b'\x00' * 32
    closing_signature = sign_balance_proof(
        tester.k2,
        1,
        token_network.address,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash,
    )
    txn_hash = token_network.transact({'from': B}).updateTransfer(
        1,
        nonce,
        transferred_amount,
        locksroot,
        additional_hash,
        closing_signature
    )
    print_gas(txn_hash, C_TOKEN_NETWORK + '.updateTransfer')

    prebalance_A = custom_token.call().balanceOf(A)
    prebalance_B = custom_token.call().balanceOf(B)

    web3.testing.mine(8)
    txn_hash = token_network.transact().settleChannel(1, A, B)
    assert custom_token.call().balanceOf(A) == prebalance_A + 20 - 15 + 5
    assert custom_token.call().balanceOf(B) == prebalance_B + 10 - 5 + 15
    print_gas(txn_hash, C_TOKEN_NETWORK + '.settleChannel')
