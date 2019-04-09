"""
A simple Python script to deploy compiled contracts.
"""
import functools
import json
import logging
from logging import getLogger
from typing import Dict, Optional

import click
from click import BadParameter
from eth_utils import is_address, to_checksum_address
from semver import compare
from web3 import HTTPProvider, Web3
from web3.middleware import geth_poa_middleware

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_TOKEN_NETWORK_REGISTRY
from raiden_contracts.contract_manager import ContractManager, contracts_precompiled_path
from raiden_contracts.deploy.contract_deployer import ContractDeployer
from raiden_contracts.deploy.contract_verifyer import ContractVerifyer
from raiden_contracts.utils.private_key import get_private_key
from raiden_contracts.utils.signature import private_key_to_address

LOG = getLogger(__name__)


def validate_address(_, _param, value):
    if not value:
        return None
    try:
        is_address(value)
        return to_checksum_address(value)
    except ValueError:
        raise click.BadParameter('must be a valid ethereum address')


def error_removed_option(message: str):
    """ Takes a message and returns a callback that raises NoSuchOption

    if the value is not None. The message is used as an argument to NoSuchOption. """
    def f(_, param, value):
        if value is not None:
            raise click.NoSuchOption(
                f'--{param.name.replace("_", "-")} is no longer a valid option. ' +
                message,
            )
    return f


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
        web3=web3,
        private_key=private_key,
        gas_limit=gas_limit,
        gas_price=gas_price,
        wait=wait,
        contracts_version=contracts_version,
    )
    ctx.obj = {}
    ctx.obj['deployer'] = deployer
    ctx.obj['deployed_contracts'] = {}
    ctx.obj['token_type'] = 'CustomToken'
    ctx.obj['wait'] = wait


@click.group(chain=True)
def main():
    pass


def contract_version_with_max_token_networks(version: Optional[str]) -> bool:
    manager = ContractManager(contracts_precompiled_path(version))
    abi = manager.get_contract_abi(CONTRACT_TOKEN_NETWORK_REGISTRY)
    constructors = list(filter(lambda x: x['type'] == 'constructor', abi))
    assert len(constructors) == 1
    inputs = constructors[0]['inputs']
    max_token_networks_args = list(filter(lambda x: x['name'] == '_max_token_networks', inputs))
    found_args = len(max_token_networks_args)
    if found_args == 0:
        return False
    elif found_args == 1:
        return True
    else:
        raise ValueError(
            "TokenNetworkRegistry's constructor has more than one arguments that are "
            'called "_max_token_networks".',
        )


def check_version_dependent_parameters(
        contracts_version: Optional[str],
        max_token_networks: Optional[int],
) -> None:
    required = contract_version_with_max_token_networks(contracts_version)
    got = max_token_networks is not None

    # For newer conracts --max-token-networks is necessary.
    if required and not got:
        raise BadParameter(
            f'For contract_version {contracts_version},'
            ' --max-token-networks option is necessary.  See --help.',
        )
    # For older contracts --max_token_networks is forbidden.
    if not required and got:
        raise BadParameter(
            f'For contract_version {contracts_version},'
            ' --max-token-networks option is forbidden'
            ' because TokenNetworkRegistry this version is not configurable this way.',
        )


@main.command()
@common_options
@click.option(
    '--save-info',
    default=True,
    help='Save deployment info to a file.',
)
@click.option(
    '--max-token-networks',
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
        max_token_networks: Optional[int],
):
    check_version_dependent_parameters(contracts_version, max_token_networks)

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
    deployed_contracts_info = deployer.deploy_raiden_contracts(
        max_num_of_token_networks=max_token_networks,
    )
    deployed_contracts = {
        contract_name: info['address']
        for contract_name, info in deployed_contracts_info['contracts'].items()
    }

    deployer.store_and_verify_deployment_info_raiden(
        deployed_contracts_info=deployed_contracts_info,
        save_info=save_info,
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

    deployed_contracts_info = deployer.deploy_service_contracts(
        token_address=token_address,
        user_deposit_whole_balance_limit=user_deposit_whole_limit,
    )
    deployed_contracts = {
        contract_name: info['address']
        for contract_name, info in deployed_contracts_info['contracts'].items()
    }

    deployer.store_and_verify_deployment_info_services(
        deployed_contracts_info=deployed_contracts_info,
        save_info=save_info,
        token_address=token_address,
        user_deposit_whole_limit=user_deposit_whole_limit,
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
    deployed_token = deployer.deploy_token_contract(
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
    callback=error_removed_option('Use --token-network-registry-address'),
    hidden=True,
    help='Renamed into --token-network-registry-address',
)
@click.option(
    '--token-network-registry-address',
    default=None,
    callback=validate_address,
    help='Address of token network registry',
)
@click.option(
    '--channel-participant-deposit-limit',
    default=None,
    type=int,
    help='Address of token network registry',
)
@click.option(
    '--token-network-deposit-limit',
    default=None,
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
        token_network_registry_address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
        registry_address,
):
    assert registry_address is None  # No longer used option
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

    if token_address:
        ctx.obj['deployed_contracts'][token_type] = token_address
    if token_network_registry_address:
        ctx.obj['deployed_contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY] = \
            token_network_registry_address

    assert CONTRACT_TOKEN_NETWORK_REGISTRY in ctx.obj['deployed_contracts']
    assert token_type in ctx.obj['deployed_contracts']
    abi = deployer.contract_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK_REGISTRY)
    register_token_network(
        deployer=deployer,
        token_registry_abi=abi,
        token_registry_address=ctx.obj['deployed_contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY],
        token_address=ctx.obj['deployed_contracts'][token_type],
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
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

    verifyer = ContractVerifyer(web3=web3, contracts_version=contracts_version)
    verifyer.verify_deployed_contracts_in_filesystem()


def contracts_version_expects_deposit_limits(contracts_version: Optional[str]) -> bool:
    if contracts_version is None:
        return True
    if contracts_version == '0.3._':
        return False
    return compare(contracts_version, '0.9.0') > -1


def register_token_network(
        deployer: ContractDeployer,
        token_registry_abi: Dict,
        token_registry_address: str,
        token_address: str,
        channel_participant_deposit_limit: Optional[int],
        token_network_deposit_limit: Optional[int],
):
    """Register token with a TokenNetworkRegistry contract."""
    with_limits = contracts_version_expects_deposit_limits(deployer.contracts_version)
    if with_limits:
        assert channel_participant_deposit_limit is not None, \
            'contracts_version 0.9.0 and afterwards expect channel_participant_deposit_limit'
        assert token_network_deposit_limit is not None, \
            'contracts_version 0.9.0 and afterwards expect token_network_deposit_limit'
    else:
        assert channel_participant_deposit_limit is None, \
            'contracts_version below 0.9.0 does not expect channel_participant_deposit_limit'
        assert token_network_deposit_limit is None, \
            'contracts_version below 0.9.0 does not expect token_network_deposit_limit'
    token_network_registry = deployer.web3.eth.contract(
        abi=token_registry_abi,
        address=token_registry_address,
    )

    version_from_onchain = token_network_registry.functions.contract_version().call()
    assert version_from_onchain == deployer.contract_manager.version_string(), \
        f'got {version_from_onchain}, expected {deployer.contract_manager.version_string()}'

    command = token_network_registry.functions.createERC20TokenNetwork(
        token_address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
    ) if with_limits else token_network_registry.functions.createERC20TokenNetwork(
        token_address,
    )
    deployer.transact(command)

    token_network_address = token_network_registry.functions.token_to_token_networks(
        token_address,
    ).call()
    token_network_address = to_checksum_address(token_network_address)

    print(
        'TokenNetwork address: {0}'.format(
            token_network_address,
        ),
    )
    return token_network_address


if __name__ == '__main__':
    main()
