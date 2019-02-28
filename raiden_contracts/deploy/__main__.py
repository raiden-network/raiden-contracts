"""
A simple Python script to deploy compiled contracts.
"""
import functools
import json
import logging
import click

from logging import getLogger
from mypy_extensions import TypedDict
from typing import Any, Dict, List, Optional

from eth_utils import denoms, encode_hex, is_address, to_checksum_address
from web3 import HTTPProvider, Web3
from web3.contract import Contract, ContractFunction
from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware


from raiden_contracts.constants import (
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_MONITORING_SERVICE,
    DEPLOY_SETTLE_TIMEOUT_MAX,
    DEPLOY_SETTLE_TIMEOUT_MIN,
    CONTRACTS_VERSION,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    contract_version_string,
    contracts_precompiled_path,
    contracts_source_path,
    contracts_deployed_path,
    Flavor,
    flavor_of_lower_name,
    get_contracts_deployed,
)
from raiden_contracts.utils.transaction import check_succesful_tx
from raiden_contracts.utils.bytecode import runtime_hexcode
from raiden_contracts.utils.private_key import get_private_key
from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.type_aliases import Address


log = getLogger(__name__)


def validate_address(ctx, param, value):
    if not value:
        return None
    try:
        is_address(value)
        return to_checksum_address(value)
    except ValueError:
        raise click.BadParameter('must be a valid ethereum address')


class ContractDeployer:
    def __init__(
        self,
        web3: Web3,
        flavor: Flavor,
        private_key: str,
        gas_limit: int,
        gas_price: int=1,
        wait: int=10,
        contracts_version: Optional[str]=None,
    ):
        self.web3 = web3
        self.flavor = flavor
        self.wait = wait
        self.owner = private_key_to_address(private_key)
        self.transaction = {'from': self.owner, 'gas': gas_limit}
        if gas_price != 0:
            self.transaction['gasPrice'] = gas_price * denoms.gwei

        self.contracts_version = contracts_version
        self.precompiled_path = contracts_precompiled_path(flavor, self.contracts_version)
        self.contract_manager = ContractManager(self.precompiled_path)
        self.web3.middleware_stack.add(
            construct_sign_and_send_raw_middleware(private_key),
        )

        # Check that the precompiled data matches the source code
        # Only for current version, because this is the only one with source code
        if self.contracts_version in [None, CONTRACTS_VERSION]:
            contract_manager_source = ContractManager(contracts_source_path(flavor))
            contract_manager_source.checksum_contracts()
            contract_manager_source.verify_precompiled_checksums(self.precompiled_path)
        else:
            log.info('Skipped checks against the source code because it is not available.')

    def deploy(
        self,
        contract_name: str,
        args=None,
    ):
        if args is None:
            args = list()
        contract_interface = self.contract_manager.get_contract(
            contract_name,
        )

        # Instantiate and deploy contract
        contract = self.web3.eth.contract(
            abi=contract_interface['abi'],
            bytecode=contract_interface['bin'],
        )

        # Get transaction hash from deployed contract
        txhash = self.send_deployment_transaction(contract, args)

        # Get tx receipt to get contract address
        log.debug(
            f'Deploying {contract_name} txHash={encode_hex(txhash)}, '
            f'contracts version {self.contract_manager.contracts_version}',
        )
        (receipt, tx) = check_succesful_tx(self.web3, txhash, self.wait)
        if not receipt['contractAddress']:  # happens with Parity
            receipt = dict(receipt)
            receipt['contractAddress'] = tx['creates']
        log.info(
            '{0} address: {1}. Gas used: {2}'.format(
                contract_name,
                receipt['contractAddress'],
                receipt['gasUsed'],
            ),
        )
        return receipt

    def transact(
        self,
        contract_method: ContractFunction,
    ):
        """ A wrapper around to_be_called.transact() that waits until the transaction succeeds. """
        txhash = contract_method.transact(self.transaction)
        log.debug(f'Sending txHash={encode_hex(txhash)}')
        (receipt, _) = check_succesful_tx(self.web3, txhash, self.wait)
        return receipt

    def send_deployment_transaction(self, contract, args):
        txhash = None
        while txhash is None:
            try:
                txhash = contract.constructor(*args).transact(
                    self.transaction,
                )
            except ValueError as ex:
                if ex.args[0]['code'] == -32015:
                    log.info(f'Deployment failed with {ex}. Retrying...')
                else:
                    raise ex

        return txhash

    def contract_version_string():
        return contract_version_string(flavor, self.contracts_manager.contracts_version)


def common_options(func):
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


def setup_ctx(
    ctx: click.Context,
    flavor: str,
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
    assert web3.eth.getBalance(owner) > 0, 'Account with insuficient funds.'
    deployer = ContractDeployer(
        web3,
        flavor_of_lower_name[flavor],
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
    '--flavor',
    type=click.Choice(['limited', 'unlimited']),
    help='Choose a flavor.',
    required=True,
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
    flavor: str,
):
    flavor_enum = flavor_of_lower_name[flavor]
    setup_ctx(
        ctx,
        flavor,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
    )
    deployer = ctx.obj['deployer']
    deployed_contracts_info = deploy_raiden_contracts(deployer)
    deployed_contracts = {
        contract_name: info['address']
        for contract_name, info in deployed_contracts_info['contracts'].items()
    }

    if save_info is True:
        store_deployment_info(deployed_contracts_info, flavor_enum)
        verify_deployed_contracts_in_filesystem(
            deployer.web3,
            deployer.contract_manager,
            flavor_enum,
        )
    else:
        verify_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            deployed_contracts_info,
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
    '--save-info',
    default=True,
    help='Save deployment info to a file.',
)
@click.option(
    '--flavor',
    type=click.Choice(['limited', 'unlimited']),
    help='Choose a flavor.',
    required=True,
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
    flavor: str,
    contracts_version,
):
    flavor_enum = flavor_of_lower_name[flavor]
    setup_ctx(
        ctx,
        flavor,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
    )
    deployer = ctx.obj['deployer']

    deployed_contracts_info = deploy_service_contracts(deployer, token_address)
    deployed_contracts = {
        contract_name: info['address']
        for contract_name, info in deployed_contracts_info['contracts'].items()
    }

    if save_info is True:
        store_deployment_info(deployed_contracts_info, flavor_enum, services=True)
        verify_deployed_service_contracts_in_filesystem(
            deployer.web3,
            flavor_enum,
            deployer.contract_manager,
            token_address,
        )
    else:
        verify_service_contracts_deployment_data(
            deployer.web3,
            deployer.contract_manager,
            token_address,
            deployed_contracts_info,
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
@click.option(
    '--flavor',
    type=click.Choice(['limited', 'unlimited']),
    help='Choose a flavor.',
    required=True,
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
    flavor,
):
    setup_ctx(
        ctx,
        flavor,
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
    '--flavor',
    type=click.Choice(['limited', 'unlimited']),
    help='Choose a flavor.',
    required=True,
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
    flavor,
):
    setup_ctx(
        ctx,
        flavor,
        private_key,
        rpc_provider,
        wait,
        gas_price,
        gas_limit,
        contracts_version,
    )
    token_type = ctx.obj['token_type']
    deployer = ctx.obj['deployer']
    expected_version = contract_version_string(flavor, contracts_version)

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
@click.option(
    '--flavor',
    type=click.Choice(['limited', 'unlimited']),
    help='Choose a flavor.',
    required=True,
)
@click.pass_context
def verify(ctx, rpc_provider, contracts_version, flavor):
    flavor_enum = flavor_of_lower_name[flavor]
    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={'timeout': 60}))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    print('Web3 provider is', web3.providers[0])

    contract_manager = ContractManager(contracts_precompiled_path(contracts_version))
    verify_deployed_contracts_in_filesystem(web3, contract_manager, flavor_enum)


def deployed_data_from_receipt(receipt, constructor_arguments):
    return {
        'address': to_checksum_address(receipt['contractAddress']),
        'transaction_hash': encode_hex(receipt['transactionHash']),
        'block_number': receipt['blockNumber'],
        'gas_cost': receipt['gasUsed'],
        'constructor_arguments': constructor_arguments,
    }


def deploy_and_remember(
        contract_name: str,
        arguments: List,
        deployer: ContractDeployer,
        deployed_contracts: "DeployedContracts",
) -> Contract:
    """ Deployes contract_name with arguments and store the result in deployed_contracts. """
    receipt = deployer.deploy(contract_name, arguments)
    deployed_contracts['contracts'][contract_name] = deployed_data_from_receipt(receipt, arguments)
    return deployer.web3.eth.contract(
        abi=deployer.contract_manager.get_contract_abi(contract_name),
        address=deployed_contracts['contracts'][contract_name]['address'],
    )


def deploy_raiden_contracts(
    deployer: ContractDeployer,
):
    """Deploy all required raiden contracts and return a dict of contract_name:address"""

    deployed_contracts: DeployedContracts = {
        'contracts_version': deployer.contract_manager.contracts_version,
        'chain_id': int(deployer.web3.version.network),
        'contracts': {},
    }

    deploy_and_remember(CONTRACT_ENDPOINT_REGISTRY, [], deployer, deployed_contracts)
    secret_registry = deploy_and_remember(
        CONTRACT_SECRET_REGISTRY,
        [],
        deployer,
        deployed_contracts,
    )
    deploy_and_remember(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        [
            secret_registry.address,
            deployed_contracts['chain_id'],
            DEPLOY_SETTLE_TIMEOUT_MIN,
            DEPLOY_SETTLE_TIMEOUT_MAX,
        ],
        deployer,
        deployed_contracts,
    )

    return deployed_contracts


def deploy_service_contracts(deployer: ContractDeployer, token_address: str):
    """Deploy 3rd party service contracts"""
    deployed_contracts: DeployedContracts = {
        'contracts_version': deployer.contract_manager.contracts_version,
        'chain_id': int(deployer.web3.version.network),
        'contracts': {},
    }

    deploy_and_remember(CONTRACT_SERVICE_REGISTRY, [token_address], deployer, deployed_contracts)
    user_deposit = deploy_and_remember(
        CONTRACT_USER_DEPOSIT,
        [token_address],
        deployer,
        deployed_contracts,
    )

    monitoring_service_constructor_args = [
        token_address,
        deployed_contracts['contracts'][CONTRACT_SERVICE_REGISTRY]['address'],
        deployed_contracts['contracts'][CONTRACT_USER_DEPOSIT]['address'],
    ]
    msc = deploy_and_remember(
        CONTRACT_MONITORING_SERVICE,
        monitoring_service_constructor_args,
        deployer,
        deployed_contracts,
    )

    one_to_n = deploy_and_remember(
        CONTRACT_ONE_TO_N,
        [user_deposit.address],
        deployer,
        deployed_contracts,
    )

    # Tell the UserDeposit instance about other contracts.
    log.debug(
        "Calling UserDeposit.init() with "
        f"msc_address={msc.address} "
        f"one_to_n_address={one_to_n.address}",
    )
    deployer.transact(user_deposit.functions.init(msc.address, one_to_n.address))

    return deployed_contracts


def deploy_token_contract(
    deployer: ContractDeployer,
    token_supply: int,
    token_decimals: int,
    token_name: str,
    token_symbol: str,
    token_type: str='CustomToken',
):
    """Deploy a token contract."""
    receipt = deployer.deploy(
        token_type,
        [token_supply, token_decimals, token_name, token_symbol],
    )
    token_address = receipt['contractAddress']
    assert token_address and is_address(token_address)
    token_address = to_checksum_address(token_address)
    return {token_type: token_address}


def register_token_network(
    web3: Web3,
    caller: str,
    token_registry_abi: Dict,
    token_registry_address: str,
    token_registry_version: str,
    token_address: str,
    wait=10,
    gas_limit=4000000,
    gas_price=10,
):
    """Register token with a TokenNetworkRegistry contract."""
    token_network_registry = web3.eth.contract(
        abi=token_registry_abi,
        address=token_registry_address,
    )

    assert token_network_registry.functions.contract_version().call() == token_registry_version, \
        f"got {token_network_registry.functions.contract_version().call()}," \
        f"expected {token_registry_version}"

    txhash = token_network_registry.functions.createERC20TokenNetwork(
        token_address,
    ).transact(
        {
            'from': caller,
            'gas': gas_limit,
            'gasPrice': gas_price * denoms.gwei,
        },
    )
    log.debug(
        "calling createERC20TokenNetwork(%s) txHash=%s" %
        (
            token_address,
            encode_hex(txhash),
        ),
    )
    (receipt, _) = check_succesful_tx(web3, txhash, wait)

    token_network_address = token_network_registry.functions.token_to_token_networks(
        token_address,
    ).call()
    token_network_address = to_checksum_address(token_network_address)

    print(
        'TokenNetwork address: {0} Gas used: {1}'.format(
            token_network_address,
            receipt['gasUsed'],
        ),
    )
    return token_network_address


def store_deployment_info(deployment_info: dict, flavor: Flavor, services: bool=False):
    deployment_file_path = contracts_deployed_path(
        deployment_info['chain_id'],
        flavor,
        deployment_info['contracts_version'],
        services,
    )
    with deployment_file_path.open(mode='w') as target_file:
        target_file.write(json.dumps(deployment_info))

    print(
        f'Deployment information for chain id = {deployment_info["chain_id"]} '
        f' has been updated at {deployment_file_path}.',
    )


def verify_deployment_data(web3: Web3, contract_manager: ContractManager, deployment_data):
    chain_id = int(web3.version.network)
    assert deployment_data is not None

    assert contract_manager.contracts_version == deployment_data['contracts_version']
    assert chain_id == deployment_data['chain_id']

    endpoint_registry, _ = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_ENDPOINT_REGISTRY,
    )

    secret_registry, _ = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_SECRET_REGISTRY,
    )

    token_network_registry, constructor_arguments = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_TOKEN_NETWORK_REGISTRY,
    )

    # We need to also check the constructor parameters against the chain
    assert to_checksum_address(
        token_network_registry.functions.secret_registry_address().call(),
    ) == secret_registry.address
    assert secret_registry.address == constructor_arguments[0]
    assert token_network_registry.functions.chain_id().call() == constructor_arguments[1]
    assert token_network_registry.functions.settlement_timeout_min().call() == \
        constructor_arguments[2]
    assert token_network_registry.functions.settlement_timeout_max().call() == \
        constructor_arguments[3]

    return True


def verify_deployed_contracts_in_filesystem(
        web3: Web3,
        contract_manager: ContractManager,
        flavor: Flavor,
):
    chain_id = int(web3.version.network)

    deployment_data = get_contracts_deployed(chain_id, flavor, contract_manager.contracts_version)
    deployment_file_path = contracts_deployed_path(
        chain_id,
        flavor,
        contract_manager.contracts_version,
    )
    assert deployment_data is not None

    if verify_deployment_data(web3, contract_manager, deployment_data):
        print(f'Deployment info from {deployment_file_path} has been verified and it is CORRECT.')


def verify_service_contracts_deployment_data(
    web3: Web3,
    contract_manager: ContractManager,
    token_address: str,
    deployment_data: dict,
):
    chain_id = int(web3.version.network)
    assert deployment_data is not None

    assert contract_manager.contracts_version == deployment_data['contracts_version']
    assert chain_id == deployment_data['chain_id']

    service_bundle, constructor_arguments = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_SERVICE_REGISTRY,
    )
    assert to_checksum_address(service_bundle.functions.token().call()) == token_address
    assert token_address == constructor_arguments[0]

    user_deposit, constructor_arguments = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_USER_DEPOSIT,
    )
    assert len(constructor_arguments) == 1
    assert to_checksum_address(user_deposit.functions.token().call()) == token_address
    assert token_address == constructor_arguments[0]

    monitoring_service, constructor_arguments = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_MONITORING_SERVICE,
    )
    assert len(constructor_arguments) == 3
    assert to_checksum_address(monitoring_service.functions.token().call()) == token_address
    assert token_address == constructor_arguments[0]

    assert to_checksum_address(
        monitoring_service.functions.service_registry().call(),
    ) == service_bundle.address
    assert service_bundle.address == constructor_arguments[1]

    assert to_checksum_address(
        monitoring_service.functions.user_deposit().call(),
    ) == user_deposit.address
    assert user_deposit.address == constructor_arguments[2]

    one_to_n, constructor_arguments = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_ONE_TO_N,
    )
    assert to_checksum_address(
        one_to_n.functions.deposit_contract().call(),
    ) == user_deposit.address
    assert user_deposit.address == constructor_arguments[0]
    assert len(constructor_arguments) == 1

    # Check that UserDeposit.init() had the right effect
    onchain_msc_address = to_checksum_address(user_deposit.functions.msc_address().call())
    assert onchain_msc_address == monitoring_service.address, \
        f"MSC address found onchain: {onchain_msc_address}, expected: {monitoring_service.address}"
    assert to_checksum_address(
        user_deposit.functions.one_to_n_address().call(),
    ) == one_to_n.address

    return True


def verify_deployed_service_contracts_in_filesystem(
    web3: Web3,
    flavor: Flavor,
    contract_manager: ContractManager,
    token_address: str,
):
    chain_id = int(web3.version.network)

    deployment_data = get_contracts_deployed(
        chain_id,
        flavor,
        contract_manager.contracts_version,
        services=True,
    )
    deployment_file_path = contracts_deployed_path(
        chain_id,
        flavor,
        contract_manager.contracts_version,
        services=True,
    )
    assert deployment_data is not None

    if verify_service_contracts_deployment_data(
            web3,
            contract_manager,
            token_address,
            deployment_data):
        print(f'Deployment info from {deployment_file_path} has been verified and it is CORRECT.')


def verify_deployed_contract(
    web3: Web3,
    contract_manager: ContractManager,
    deployment_data: dict,
    contract_name: str,
) -> Contract:
    """ Verify deployment info against the chain

    Verifies:
    - the runtime bytecode - precompiled data against the chain
    - information stored in deployment_*.json against the chain,
    except for the constructor arguments, which have to be checked
    separately.

    Returns: (onchain_instance, constructor_arguments)
    """
    contracts = deployment_data['contracts']

    contract_address = contracts[contract_name]['address']
    contract_instance = web3.eth.contract(
        abi=contract_manager.get_contract_abi(contract_name),
        address=contract_address,
    )

    # Check that the deployed bytecode matches the precompiled data
    blockchain_bytecode = web3.eth.getCode(contract_address).hex()
    compiled_bytecode = runtime_hexcode(contract_manager, contract_name)
    assert blockchain_bytecode == compiled_bytecode

    print(
        f'{contract_name} at {contract_address} '
        f'matches the compiled data from contracts.json',
    )

    # Check blockchain transaction hash & block information
    receipt = web3.eth.getTransactionReceipt(
        contracts[contract_name]['transaction_hash'],
    )
    assert receipt['blockNumber'] == contracts[contract_name]['block_number'], (
        f"We have block_number {contracts[contract_name]['block_number']} "
        f"instead of {receipt['blockNumber']}"
    )
    assert receipt['gasUsed'] == contracts[contract_name]['gas_cost'], (
        f"We have gasUsed {contracts[contract_name]['gas_cost']} "
        f"instead of {receipt['gasUsed']}"
    )
    assert receipt['contractAddress'] == contracts[contract_name]['address'], (
        f"We have contractAddress {contracts[contract_name]['address']} "
        f"instead of {receipt['contractAddress']}"
    )

    # Check the contract version
    version = contract_instance.functions.contract_version().call()
    assert version == deployment_data['contracts_version']

    return contract_instance, contracts[contract_name]['constructor_arguments']


# Classes for static type checking of deployed_contracts dictionary.

class DeployedContract(TypedDict):
    address: Address
    transaction_hash: str
    block_number: int
    gas_cost: int
    constructor_arguments: Any


class DeployedContracts(TypedDict):
    chain_id: int
    contracts: Dict[str, DeployedContract]
    contracts_version: str


if __name__ == '__main__':
    main()
