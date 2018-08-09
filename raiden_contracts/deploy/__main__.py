"""
A simple Python script to deploy compiled contracts.
"""
import logging
from logging import getLogger
from getpass import getpass

import click
import json

from raiden_contracts.contract_manager import ContractManager, CONTRACTS_SOURCE_DIRS
from web3 import Web3, HTTPProvider
from eth_utils import (
    is_address,
    to_checksum_address,
)

from raiden_contracts.utils.utils import (
    check_succesful_tx,
)
from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_CUSTOM_TOKEN,
    DEPLOY_SETTLE_TIMEOUT_MIN,
    DEPLOY_SETTLE_TIMEOUT_MAX,
)
from web3.middleware import geth_poa_middleware

log = getLogger(__name__)


@click.command()
@click.option(
    '--rpc-provider',
    default='http://127.0.0.1:8545',
    help='Address of the Ethereum RPC provider',
)
@click.option(
    '--owner',
    help='Contracts owner, default: web3.eth.accounts[0]',
)
@click.option(
    '--wait',
    default=300,
    help='Max tx wait time in s.',
)
@click.option(
    '--gas-price',
    default=0,
    type=int,
    help='Gas price to use in gwei',
)
@click.option(
    '--gas-limit',
    default=5_500_00,
)
@click.option(
    '--deploy-token',
    is_flag=True,
    help='Also deploy a test token and register with the newly deployed token network contract')
@click.option(
    '--supply',
    default=10000000,
    help='Token contract supply (number of total issued tokens).',
)
@click.option(
    '--token-name',
    default=CONTRACT_CUSTOM_TOKEN,
    help='Token contract name.',
)
@click.option(
    '--token-decimals',
    default=18,
    help='Token contract number of decimals.',
)
@click.option(
    '--token-symbol',
    default='TKN',
    help='Token contract symbol.',
)
@click.option(
    '--token-address',
    help='Already deployed token address.',
)
def main(
    rpc_provider,
    owner,
    wait,
    gas_price,
    gas_limit,
    deploy_token,
    supply,
    token_name,
    token_decimals,
    token_symbol,
    token_address,
):
    supply *= 10 ** token_decimals

    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('web3').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.INFO)

    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={'timeout': 60}))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    print('Web3 provider is', web3.providers[0])

    owner = owner or web3.eth.accounts[0]
    assert owner and is_address(owner), 'Invalid owner provided.'
    owner = to_checksum_address(owner)
    print('Owner is', owner)
    assert web3.eth.getBalance(owner) > 0, 'Account with insuficient funds.'

    password = getpass(f'Enter password for {owner}:')

    transaction = {'from': owner, 'gas': gas_limit}
    if gas_price != 0:
        transaction['gasPrice'] = gas_price * 10 ** 9

    contract_manager = ContractManager(CONTRACTS_SOURCE_DIRS)
    contract_manager._compile_all_contracts()
    contracts_compiled_data = contract_manager._contracts

    deployed_contracts = {}

    web3.personal.unlockAccount(owner, password)
    deployed_contracts[CONTRACT_ENDPOINT_REGISTRY] = deploy_contract(
        web3,
        contracts_compiled_data,
        CONTRACT_ENDPOINT_REGISTRY,
        transaction,
        wait,
    )

    web3.personal.unlockAccount(owner, password)
    secret_registry_address = deploy_contract(
        web3,
        contracts_compiled_data,
        CONTRACT_SECRET_REGISTRY,
        transaction,
        wait,
    )
    deployed_contracts[CONTRACT_SECRET_REGISTRY] = secret_registry_address

    web3.personal.unlockAccount(owner, password)
    token_network_registry_address = deploy_contract(
        web3,
        contracts_compiled_data,
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        transaction,
        wait,
        [
            secret_registry_address,
            int(web3.version.network),
            DEPLOY_SETTLE_TIMEOUT_MIN,
            DEPLOY_SETTLE_TIMEOUT_MAX,
        ],
    )
    deployed_contracts[CONTRACT_TOKEN_NETWORK_REGISTRY] = token_network_registry_address

    if deploy_token:
        if not token_address:
            web3.personal.unlockAccount(owner, password)
            deployed_contracts['CustomToken'] = token_address = deploy_contract(
                web3,
                contracts_compiled_data,
                'CustomToken',
                transaction,
                wait,
                [supply, token_decimals, token_name, token_symbol],
            )

        assert token_address and is_address(token_address)
        token_address = to_checksum_address(token_address)

        token_network_registry = instantiate_contract(
            web3,
            contracts_compiled_data,
            CONTRACT_TOKEN_NETWORK_REGISTRY,
            token_network_registry_address,
        )

        web3.personal.unlockAccount(owner, password)
        txhash = token_network_registry.transact(transaction).createERC20TokenNetwork(
            token_address,
        )
        receipt = check_succesful_tx(web3, txhash, wait)

        print(
            'TokenNetwork address: {0}. Gas used: {1}'.format(
                token_network_registry.functions.token_to_token_networks(token_address).call(),
                receipt['gasUsed'],
            ),
        )
    print(json.dumps(deployed_contracts, indent=4))


def instantiate_contract(web3, contracts_compiled_data, contract_name, contract_address):
    contract_interface = contracts_compiled_data[contract_name]

    contract = web3.eth.contract(
        abi=contract_interface['abi'],
        bytecode=contract_interface['bin'],
        address=contract_address,
    )

    return contract


def deploy_contract(
        web3,
        contracts_compiled_data,
        contract_name,
        transaction,
        txn_wait=200,
        args=None,
):
    contract_interface = contracts_compiled_data[contract_name]

    # Instantiate and deploy contract
    contract = web3.eth.contract(
        abi=contract_interface['abi'],
        bytecode=contract_interface['bin'],
    )

    log.info(f'Deploying {contract_name}')
    # Get transaction hash from deployed contract
    txhash = contract.deploy(transaction=transaction, args=args)

    # Get tx receipt to get contract address
    log.debug(f"TxHash: {txhash}")
    receipt = check_succesful_tx(web3, txhash, txn_wait)
    log.info(
        '{0} address: {1}. Gas used: {2}'.format(
            contract_name,
            receipt['contractAddress'],
            receipt['gasUsed'],
        ),
    )
    return receipt['contractAddress']


if __name__ == '__main__':
    main()
