"""
A simple Python script to deploy compiled contracts.
"""
import functools
import json
import logging
import click

from logging import getLogger
from mypy_extensions import TypedDict
from typing import Any, Dict, Optional

from eth_utils import denoms, encode_hex, is_address, to_checksum_address
from web3 import HTTPProvider, Web3
from web3.contract import Contract
from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware


from raiden_contracts.constants import (
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    DEPLOY_SETTLE_TIMEOUT_MAX,
    DEPLOY_SETTLE_TIMEOUT_MIN,
    CONTRACTS_VERSION,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    contracts_precompiled_path,
    contracts_source_path,
    contracts_deployed_path,
    get_contracts_deployed,
)
from raiden_contracts.utils.transaction import check_succesful_tx
from raiden_contracts.utils.bytecode import runtime_hexcode
from raiden_contracts.utils.private_key import get_private_key
from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.types import Address


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
        private_key: str,
        gas_limit: int,
        gas_price: int=1,
        wait: int=10,
        contracts_version: Optional[str]=None,
    ):
        self.web3 = web3
        self.wait = wait
        self.owner = private_key_to_address(private_key)
        self.transaction = {'from': self.owner, 'gas': gas_limit}
        if gas_price != 0:
            self.transaction['gasPrice'] = gas_price * denoms.gwei

        self.contracts_version = contracts_version
        self.precompiled_path = contracts_precompiled_path(self.contracts_version)
        self.contract_manager = ContractManager(self.precompiled_path)
        self.web3.middleware_stack.add(
            construct_sign_and_send_raw_middleware(private_key),
        )

        # Check that the precompiled data matches the source code
        # Only for current version, because this is the only one with source code
        if self.contracts_version in [None, CONTRACTS_VERSION]:
            contract_manager_source = ContractManager(contracts_source_path())
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
):
    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit, contracts_version)
    deployer = ctx.obj['deployer']
    deployed_contracts_info = deploy_raiden_contracts(deployer)
    deployed_contracts = {
        contract_name: info['address']
        for contract_name, info in deployed_contracts_info['contracts'].items()
    }

    if save_info is True:
        store_deployment_info(deployed_contracts_info)
        verify_deployed_contracts(deployer.web3, deployer.contract_manager)
    else:
        verify_deployed_contracts(
            deployer.web3,
            deployer.contract_manager,
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
    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit, contracts_version)
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
):
    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit, contracts_version)
    token_type = ctx.obj['token_type']
    deployer = ctx.obj['deployer']

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
    verify_deployed_contracts(web3, contract_manager)


def deploy_raiden_contracts(
    deployer: ContractDeployer,
):
    """Deploy all required raiden contracts and return a dict of contract_name:address"""

    deployed_contracts: DeployedContracts = {
        'contracts_version': deployer.contract_manager.contracts_version,
        'chain_id': int(deployer.web3.version.network),
        'contracts': {},
    }

    endpoint_registry_receipt = deployer.deploy(CONTRACT_ENDPOINT_REGISTRY)
    deployed_contracts['contracts'][CONTRACT_ENDPOINT_REGISTRY] = {
        'address': to_checksum_address(
            endpoint_registry_receipt['contractAddress'],
        ),
        'transaction_hash': encode_hex(endpoint_registry_receipt['transactionHash']),
        'block_number': endpoint_registry_receipt['blockNumber'],
        'gas_cost': endpoint_registry_receipt['gasUsed'],
        'constructor_arguments': [],
    }

    secret_registry_receipt = deployer.deploy(CONTRACT_SECRET_REGISTRY)
    deployed_contracts['contracts'][CONTRACT_SECRET_REGISTRY] = {
        'address': to_checksum_address(
            secret_registry_receipt['contractAddress'],
        ),
        'transaction_hash': encode_hex(secret_registry_receipt['transactionHash']),
        'block_number': secret_registry_receipt['blockNumber'],
        'gas_cost': secret_registry_receipt['gasUsed'],
        'constructor_arguments': [],
    }

    token_network_constructor_arguments = [
        deployed_contracts['contracts'][CONTRACT_SECRET_REGISTRY]['address'],
        deployed_contracts['chain_id'],
        DEPLOY_SETTLE_TIMEOUT_MIN,
        DEPLOY_SETTLE_TIMEOUT_MAX,
    ]
    token_network_registry_receipt = deployer.deploy(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        token_network_constructor_arguments,
    )
    deployed_contracts['contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY] = {
        'address': to_checksum_address(
            token_network_registry_receipt['contractAddress'],
        ),
        'transaction_hash': encode_hex(token_network_registry_receipt['transactionHash']),
        'block_number': token_network_registry_receipt['blockNumber'],
        'gas_cost': token_network_registry_receipt['gasUsed'],
        'constructor_arguments': token_network_constructor_arguments,
    }

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
    token_address: str,
    wait=10,
    gas_limit=4000000,
):
    """Register token with a TokenNetworkRegistry contract."""
    token_network_registry = web3.eth.contract(
        abi=token_registry_abi,
        address=token_registry_address,
    )
    txhash = token_network_registry.functions.createERC20TokenNetwork(
        token_address,
    ).transact(
        {
            'from': caller,
            'gas': gas_limit,
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


def store_deployment_info(deployment_info: dict):
    deployment_file_path = contracts_deployed_path(
        deployment_info['chain_id'],
        deployment_info['contracts_version'],
    )
    with deployment_file_path.open(mode='w') as target_file:
        target_file.write(json.dumps(deployment_info))

    print(
        f'Deployment information for chain id = {deployment_info["chain_id"]} '
        f' has been updated at {deployment_file_path}.',
    )


def verify_deployed_contracts(web3: Web3, contract_manager: ContractManager, deployment_data=None):
    chain_id = int(web3.version.network)
    deployment_file_path = None

    if deployment_data is None:
        deployment_data = get_contracts_deployed(chain_id, contract_manager.contracts_version)
        deployment_file_path = contracts_deployed_path(
            chain_id,
            contract_manager.contracts_version,
        )
    assert deployment_data is not None

    assert contract_manager.contracts_version == deployment_data['contracts_version']
    assert chain_id == deployment_data['chain_id']

    endpoint_registry = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_ENDPOINT_REGISTRY,
    )
    print(
        f'{CONTRACT_ENDPOINT_REGISTRY} at {endpoint_registry.address} '
        f'matches the compiled data from contracts.json',
    )

    secret_registry = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_SECRET_REGISTRY,
    )
    print(
        f'{CONTRACT_SECRET_REGISTRY} at {secret_registry.address} '
        f'matches the compiled data from contracts.json',
    )

    token_network_registry = verify_deployed_contract(
        web3,
        contract_manager,
        deployment_data,
        CONTRACT_TOKEN_NETWORK_REGISTRY,
    )

    # We need to also check the constructor parameters against the chain
    constructor_arguments = deployment_data['contracts'][
        CONTRACT_TOKEN_NETWORK_REGISTRY
    ]['constructor_arguments']
    assert to_checksum_address(
        token_network_registry.functions.secret_registry_address().call(),
    ) == secret_registry.address
    assert secret_registry.address == constructor_arguments[0]

    chain_id = token_network_registry.functions.chain_id().call()
    assert chain_id == constructor_arguments[1]

    settlement_timeout_min = token_network_registry.functions.settlement_timeout_min().call()
    settlement_timeout_max = token_network_registry.functions.settlement_timeout_max().call()
    assert settlement_timeout_min == constructor_arguments[2]
    assert settlement_timeout_max == constructor_arguments[3]

    print(
        f'{CONTRACT_TOKEN_NETWORK_REGISTRY} at {token_network_registry.address} '
        f'matches the compiled data from contracts.json',
    )

    if deployment_file_path is not None:
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

    return contract_instance


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
