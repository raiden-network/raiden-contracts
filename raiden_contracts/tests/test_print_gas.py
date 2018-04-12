from raiden_contracts.utils.config import (
    C_TOKEN_NETWORK_REGISTRY,
    C_TOKEN_NETWORK,
    C_SECRET_REGISTRY
)


def test_token_network_registry(chain, token_network_registry, custom_token, print_gas):
    TokenNetworkRegistry = chain.provider.get_contract_factory(C_TOKEN_NETWORK_REGISTRY)
    deploy_txn_hash = TokenNetworkRegistry.deploy(
        args=[custom_token.address, int(chain.web3.version.network)]
    )
    print_gas(deploy_txn_hash, C_TOKEN_NETWORK_REGISTRY + ' DEPLOYMENT')

    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)
    print_gas(txn_hash, C_TOKEN_NETWORK_REGISTRY + '.createERC20TokenNetwork')


def test_token_network_deployment(
        chain,
        print_gas,
        custom_token,
        secret_registry,
        token_network_registry
):
    TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
    deploy_txn_hash = TokenNetwork.deploy(args=[
        custom_token.address,
        secret_registry.address,
        int(chain.web3.version.network)
    ])

    print_gas(deploy_txn_hash, C_TOKEN_NETWORK + ' DEPLOYMENT')


def test_token_network_create(
        chain,
        print_gas,
        custom_token,
        secret_registry,
        token_network_registry
):
    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)

    print_gas(txn_hash, C_TOKEN_NETWORK_REGISTRY + ' createERC20TokenNetwork')


def test_secret_registry(secret_registry, print_gas):
    secret = b'secretsecretsecretsecretsecretse'
    txn_hash = secret_registry.transact().registerSecret(secret)
    print_gas(txn_hash, C_SECRET_REGISTRY + '.registerSecret')


def test_channel_cycle(
        web3,
        token_network,
        custom_token,
        get_accounts,
        print_gas,
        create_balance_proof
):
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

    balance_proof_A = create_balance_proof(1, A, 10, 0, 5)
    balance_proof_B = create_balance_proof(1, B, 5, 0, 3)
    balance_proof_BA = create_balance_proof(1, B, 10, 0, 5)

    txn_hash = token_network.transact({'from': A}).closeChannel(*balance_proof_B)
    print_gas(txn_hash, C_TOKEN_NETWORK + '.closeChannel')

    txn_hash = token_network.transact({'from': B}).updateTransfer(
        *balance_proof_A,
        balance_proof_BA[3]
    )
    print_gas(txn_hash, C_TOKEN_NETWORK + '.updateTransfer')

    prebalance_A = custom_token.call().balanceOf(A)
    prebalance_B = custom_token.call().balanceOf(B)

    web3.testing.mine(8)
    txn_hash = token_network.transact().settleChannel(1, A, 10, 0, b'', b'', B, 5, 0, b'', b'')
    assert custom_token.call().balanceOf(A) == prebalance_A + 20 - 10 + 5
    assert custom_token.call().balanceOf(B) == prebalance_B + 10 - 5 + 10
    print_gas(txn_hash, C_TOKEN_NETWORK + '.settleChannel')
