"""
A simple Python script to deploy compiled contracts.
"""
import functools
import json
import logging
import click

from logging import getLogger

from web3 import HTTPProvider, Web3
from web3.middleware import geth_poa_middleware


from raiden_contracts.constants import (
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    contract_version_string,
    contracts_precompiled_path,
)
from raiden_contracts.deploy.deploy import (
    ContractDeployer,
    deploy_raiden_contracts,
    deploy_service_contracts,
    deploy_token_contract,
    register_token_network,
    store_deployment_info,
    validate_address,
    verify_deployed_contracts_in_filesystem,
    verify_deployed_service_contracts_in_filesystem,
    verify_deployment_data,
    verify_service_contracts_deployment_data,
)
from raiden_contracts.utils.private_key import get_private_key
from raiden_contracts.utils.signature import private_key_to_address


LOG = getLogger(__name__)


def common_options(func):
    """A decorator that combines commonly appearing @click.option decorators."""
    @click.option(
        '--private-key',
        required=True,
        help='Path to a private key store.',
    )
    @click.option(
        '--rpc-provider',
        default='http://127.0.0.1:8545',
        help='Address of the Ethereum RPC provider',
    )
    @click.option(
        '--wait',
        default=300,
        help='Max tx wait time in s.',
    )
    @click.option(
        '--gas-price',
        default=5,
        type=int,
        help='Gas price to use in gwei',
    )
    @click.option(
        '--gas-limit',
        default=5_500_000,
    )
    @click.option(
        '--contracts-version',
        default=None,
        help='Contracts version to verify. Current version will be used by default.',
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


# pylint: disable=R0913
def setup_ctx(
        ctx: click.Context,
        private_key: str,
        rpc_provider: str,
        wait: int,
        gas_price: int,
        gas_limit: int,
        contracts_version: None = None,
):
    """Set up deployment context according to common options (shared among all
    subcommands).
    """

    if private_key is None:
        return
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('web3').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.INFO)

    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={'timeout': 60}))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    print('Web3 provider is', web3.providers[0])
    private_key = get_private_key(private_key)
    assert private_key is not None
    owner = private_key_to_address(private_key)
    # pylint: disable=E1101
    assert web3.eth.getBalance(owner) > 0, 'Account with insuficient funds.'
    deployer = ContractDeployer(
        web3,
        private_key,
        gas_limit,
        gas_price,
        wait,
        contracts_version,
    )
    ctx.obj = {}
    ctx.obj['deployer'] = deployer
    ctx.obj['deployed_contracts'] = {}
    ctx.obj['token_type'] = 'CustomToken'
    ctx.obj['wait'] = wait


@click.group(chain=True)
def main():
    pass


@main.command()
@common_options
@click.option(
    '--save-info',
    default=True,
    help='Save deployment info to a file.',
)
@click.option(
    '--max-token-networks',
    required=True,
    help='The maximum number of tokens that can be registered.',
    type=int,
)
@click.pass_context
def raiden(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        save_info,
        contracts_version,
        max_token_networks: int,
):
    setup_ctx(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
    )
    deployer = ctx.obj['deployer']
    deployed_contracts_info = deploy_raiden_contracts(
        deployer=deployer,
        max_num_of_token_networks=max_token_networks,
    )
    deployed_contracts = {
        contract_name: info['address']
        for contract_name, info in deployed_contracts_info['contracts'].items()
    }

    if save_info is True:
        store_deployment_info(deployed_contracts_info)
        verify_deployed_contracts_in_filesystem(
            deployer.web3,
            deployer.contract_manager,
        )
    else:
        verify_deployment_data(
            web3=deployer.web3,
            contract_manager=deployer.contract_manager,
            deployment_data=deployed_contracts_info,
        )

    print(json.dumps(deployed_contracts, indent=4))
    ctx.obj['deployed_contracts'].update(deployed_contracts)


@main.command()
@common_options
@click.option(
    '--token-address',
    default=None,
    callback=validate_address,
    help='Address of token used to pay for the services (MS, PFS).',
)
@click.option(
    '--user-deposit-whole-limit',
    required=True,
    type=int,
    help='Maximum amount of tokens deposited in UserDeposit',
)
@click.option(
    '--save-info',
    default=True,
    help='Save deployment info to a file.',
)
@click.pass_context
def services(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        token_address,
        save_info,
        contracts_version,
        user_deposit_whole_limit: int,
):
    setup_ctx(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
    )
    deployer = ctx.obj['deployer']

    deployed_contracts_info = deploy_service_contracts(
        deployer=deployer,
        token_address=token_address,
        user_deposit_whole_balance_limit=user_deposit_whole_limit,
    )
    deployed_contracts = {
        contract_name: info['address']
        for contract_name, info in deployed_contracts_info['contracts'].items()
    }

    if save_info is True:
        store_deployment_info(deployed_contracts_info, services=True)
        verify_deployed_service_contracts_in_filesystem(
            web3=deployer.web3,
            contract_manager=deployer.contract_manager,
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_limit,
        )
    else:
        verify_service_contracts_deployment_data(
            web3=deployer.web3,
            contract_manager=deployer.contract_manager,
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_limit,
            deployment_data=deployed_contracts_info,
        )

    print(json.dumps(deployed_contracts, indent=4))
    ctx.obj['deployed_contracts'].update(deployed_contracts)


@main.command()
@common_options
@click.option(
    '--token-supply',
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
@click.pass_context
def token(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
        token_supply,
        token_name,
        token_decimals,
        token_symbol,
):
    setup_ctx(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
    )
    deployer = ctx.obj['deployer']
    token_supply *= 10 ** token_decimals
    deployed_token = deploy_token_contract(
        deployer,
        token_supply,
        token_decimals,
        token_name,
        token_symbol,
        token_type=ctx.obj['token_type'],
    )
    print(json.dumps(deployed_token, indent=4))
    ctx.obj['deployed_contracts'].update(deployed_token)


@main.command()
@common_options
@click.option(
    '--token-address',
    default=None,
    callback=validate_address,
    help='Already deployed token address.',
)
@click.option(
    '--registry-address',
    default=None,
    callback=validate_address,
    help='Address of token network registry',
)
@click.option(
    '--channel-participant-deposit-limit',
    required=True,
    type=int,
    help='Address of token network registry',
)
@click.option(
    '--token-network-deposit-limit',
    required=True,
    type=int,
    help='Address of token network registry',
)
@click.pass_context
def register(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
        token_address,
        registry_address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    setup_ctx(
        ctx,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
    )
    token_type = ctx.obj['token_type']
    deployer = ctx.obj['deployer']
    expected_version = contract_version_string(contracts_version)

    if token_address:
        ctx.obj['deployed_contracts'][token_type] = token_address
    if registry_address:
        ctx.obj['deployed_contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY] = registry_address

    assert CONTRACT_TOKEN_NETWORK_REGISTRY in ctx.obj['deployed_contracts']
    assert token_type in ctx.obj['deployed_contracts']
    abi = deployer.contract_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK_REGISTRY)
    register_token_network(
        web3=deployer.web3,
        caller=deployer.owner,
        token_registry_abi=abi,
        token_registry_address=ctx.obj['deployed_contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY],
        token_address=ctx.obj['deployed_contracts'][token_type],
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
        wait=ctx.obj['wait'],
        gas_price=gas_price,
        token_registry_version=expected_version,
    )


@main.command()
@click.option(
    '--rpc-provider',
    default='http://127.0.0.1:8545',
    help='Address of the Ethereum RPC provider',
)
@click.option(
    '--contracts-version',
    help='Contracts version to verify. Current version will be used by default.',
)
@click.pass_context
def verify(ctx, rpc_provider, contracts_version):
    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={'timeout': 60}))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    print('Web3 provider is', web3.providers[0])

    contract_manager = ContractManager(contracts_precompiled_path(contracts_version))
    verify_deployed_contracts_in_filesystem(web3, contract_manager)


if __name__ == '__main__':
    main()
