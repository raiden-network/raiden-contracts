"""
A simple Python script to deploy compiled contracts.
"""
import functools
import json
import logging
from logging import getLogger
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import click
from click import BadParameter, Context, Option, Parameter
from eth_typing.evm import ChecksumAddress, HexAddress
from eth_utils import is_address, to_checksum_address
from web3 import HTTPProvider, Web3
from web3.middleware import geth_poa_middleware

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_TOKEN_NETWORK_REGISTRY
from raiden_contracts.deploy.contract_deployer import ContractDeployer
from raiden_contracts.deploy.contract_verifier import ContractVerifier
from raiden_contracts.utils.private_key import get_private_key
from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.versions import contract_version_with_max_token_networks

LOG = getLogger(__name__)


def validate_address(
    _: Context, _param: Union[Option, Parameter], value: Optional[str]
) -> Optional[ChecksumAddress]:
    if not value:
        return None
    try:
        is_address(value)
        return to_checksum_address(value)
    except ValueError:
        raise click.BadParameter("must be a valid ethereum address")


def error_removed_option(message: str) -> Callable:
    """ Takes a message and returns a callback that raises NoSuchOption

    if the value is not None. The message is used as an argument to NoSuchOption. """

    def f(_: Any, param: Parameter, value: Any) -> None:
        if value is not None:
            raise click.NoSuchOption(
                f'--{param.name.replace("_", "-")} is no longer a valid option. ' + message
            )

    return f


def common_options(func: Callable) -> Callable:
    """A decorator that combines commonly appearing @click.option decorators."""

    @click.option("--private-key", required=True, help="Path to a private key store.")
    @click.option(
        "--rpc-provider",
        default="http://127.0.0.1:8545",
        help="Address of the Ethereum RPC provider",
    )
    @click.option("--wait", default=300, help="Max tx wait time in s.")
    @click.option("--gas-price", default=5, type=int, help="Gas price to use in gwei")
    @click.option("--gas-limit", default=5_500_000)
    @click.option(
        "--contracts-version",
        default=None,
        help="Contracts version to verify. Current version will be used by default.",
    )
    @functools.wraps(func)
    def wrapper(*args: List, **kwargs: Dict) -> Any:
        return func(*args, **kwargs)

    return wrapper


# pylint: disable=R0913
def setup_ctx(
    ctx: click.Context,
    private_key: Optional[str],
    rpc_provider: str,
    wait: int,
    gas_price: int,
    gas_limit: int,
    contracts_version: Optional[str] = None,
) -> None:
    """Set up deployment context according to common options (shared among all
    subcommands).
    """

    if private_key is None:
        return
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("web3").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.INFO)

    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={"timeout": 60}))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    print("Web3 provider is", web3.providers[0])
    private_key_string = get_private_key(Path(private_key))
    if not private_key_string:
        raise RuntimeError("Could not access the private key.")
    owner = private_key_to_address(private_key_string)
    # pylint: disable=E1101
    if web3.eth.getBalance(owner) == 0:
        raise RuntimeError("Account with insufficient funds.")
    deployer = ContractDeployer(
        web3=web3,
        private_key=private_key_string,
        gas_limit=gas_limit,
        gas_price=gas_price,
        wait=wait,
        contracts_version=contracts_version,
    )
    ctx.obj = {}
    ctx.obj["deployer"] = deployer
    ctx.obj["deployed_contracts"] = {}
    ctx.obj["token_type"] = "CustomToken"
    ctx.obj["wait"] = wait


@click.group(chain=True)
def main() -> int:
    pass


def check_version_dependent_parameters(
    contracts_version: Optional[str], max_token_networks: Optional[int]
) -> None:
    required = contract_version_with_max_token_networks(contracts_version)
    got = max_token_networks is not None

    # For newer conracts --max-token-networks is necessary.
    if required and not got:
        raise BadParameter(
            f"For contract_version {contracts_version},"
            " --max-token-networks option is necessary.  See --help."
        )
    # For older contracts --max_token_networks is forbidden.
    if not required and got:
        raise BadParameter(
            f"For contract_version {contracts_version},"
            " --max-token-networks option is forbidden"
            " because TokenNetworkRegistry this version is not configurable this way."
        )


@main.command()
@common_options
@click.option("--save-info/--no-save-info", default=True, help="Save deployment info to a file.")
@click.option(
    "--max-token-networks", help="The maximum number of tokens that can be registered.", type=int
)
@click.pass_context
def raiden(
    ctx: click.Context,
    private_key: Optional[str],
    rpc_provider: str,
    wait: int,
    gas_price: int,
    gas_limit: int,
    save_info: int,
    contracts_version: Optional[str],
    max_token_networks: Optional[int],
) -> None:
    check_version_dependent_parameters(contracts_version, max_token_networks)

    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit, contracts_version)
    deployer = ctx.obj["deployer"]
    deployed_contracts_info = deployer.deploy_raiden_contracts(
        max_num_of_token_networks=max_token_networks
    )
    deployed_contracts = {
        contract_name: info["address"]
        for contract_name, info in deployed_contracts_info["contracts"].items()
    }

    if save_info:
        deployer.store_and_verify_deployment_info_raiden(
            deployed_contracts_info=deployed_contracts_info
        )
    else:
        deployer.verify_deployment_data(deployed_contracts_info=deployed_contracts_info)

    print(json.dumps(deployed_contracts, indent=4))
    ctx.obj["deployed_contracts"].update(deployed_contracts)


@main.command()
@common_options
@click.option(
    "--token-address",
    default=None,
    callback=validate_address,
    help="Address of token used to pay for the services (MS, PFS).",
)
@click.option(
    "--user-deposit-whole-limit",
    required=True,
    type=int,
    help="Maximum amount of tokens deposited in UserDeposit",
)
@click.option("--save-info/--no-save-info", default=True, help="Save deployment info to a file.")
@click.pass_context
def services(
    ctx: Context,
    private_key: Optional[str],
    rpc_provider: str,
    wait: int,
    gas_price: int,
    gas_limit: int,
    token_address: HexAddress,
    save_info: bool,
    contracts_version: Optional[str],
    user_deposit_whole_limit: int,
) -> None:
    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit, contracts_version)
    deployer: ContractDeployer = ctx.obj["deployer"]

    deployed_contracts_info = deployer.deploy_service_contracts(
        token_address=token_address, user_deposit_whole_balance_limit=user_deposit_whole_limit
    )
    deployed_contracts = {
        contract_name: info["address"]
        for contract_name, info in deployed_contracts_info["contracts"].items()
    }

    if save_info:
        deployer.store_and_verify_deployment_info_services(
            deployed_contracts_info=deployed_contracts_info,
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_limit,
        )
    else:
        deployer.verify_service_contracts_deployment_data(
            deployed_contracts_info=deployed_contracts_info,
            token_address=token_address,
            user_deposit_whole_balance_limit=user_deposit_whole_limit,
        )

    print(json.dumps(deployed_contracts, indent=4))
    ctx.obj["deployed_contracts"].update(deployed_contracts)


@main.command()
@common_options
@click.option(
    "--token-supply",
    default=10000000,
    help="Token contract supply (number of total issued tokens).",
)
@click.option("--token-name", default=CONTRACT_CUSTOM_TOKEN, help="Token contract name.")
@click.option("--token-decimals", default=18, help="Token contract number of decimals.")
@click.option("--token-symbol", default="TKN", help="Token contract symbol.")
@click.pass_context
def token(
    ctx: click.Context,
    private_key: Optional[str],
    rpc_provider: str,
    wait: int,
    gas_price: int,
    gas_limit: int,
    contracts_version: Optional[str],
    token_supply: int,
    token_name: str,
    token_decimals: int,
    token_symbol: str,
) -> None:
    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit, contracts_version)
    deployer = ctx.obj["deployer"]
    token_supply *= 10 ** token_decimals
    deployed_token = deployer.deploy_token_contract(
        token_supply, token_decimals, token_name, token_symbol, token_type=ctx.obj["token_type"]
    )
    print(json.dumps(deployed_token, indent=4))
    ctx.obj["deployed_contracts"].update(deployed_token)


@main.command()
@common_options
@click.option(
    "--token-address",
    default=None,
    callback=validate_address,
    help="Already deployed token address.",
)
@click.option(
    "--registry-address",
    default=None,
    callback=error_removed_option("Use --token-network-registry-address"),
    hidden=True,
    help="Renamed into --token-network-registry-address",
)
@click.option(
    "--token-network-registry-address",
    default=None,
    callback=validate_address,
    help="Address of token network registry",
)
@click.option(
    "--channel-participant-deposit-limit",
    default=None,
    type=int,
    help="Address of token network registry",
)
@click.option(
    "--token-network-deposit-limit",
    default=None,
    type=int,
    help="Address of token network registry",
)
@click.pass_context
def register(
    ctx: Context,
    private_key: str,
    rpc_provider: str,
    wait: int,
    gas_price: int,
    gas_limit: int,
    contracts_version: str,
    token_address: HexAddress,
    token_network_registry_address: HexAddress,
    channel_participant_deposit_limit: Optional[int],
    token_network_deposit_limit: Optional[int],
    registry_address: Optional[HexAddress],
) -> None:
    assert registry_address is None  # No longer used option
    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit, contracts_version)
    token_type = ctx.obj["token_type"]
    deployer = ctx.obj["deployer"]

    if token_address:
        ctx.obj["deployed_contracts"][token_type] = token_address
    if token_network_registry_address:
        ctx.obj["deployed_contracts"][
            CONTRACT_TOKEN_NETWORK_REGISTRY
        ] = token_network_registry_address

    if CONTRACT_TOKEN_NETWORK_REGISTRY not in ctx.obj["deployed_contracts"]:
        raise RuntimeError(
            "No TokenNetworkRegistry was specified. "
            "Add --token-network-registry-address <address>."
        )
    assert token_type in ctx.obj["deployed_contracts"]
    abi = deployer.contract_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK_REGISTRY)
    deployer.register_token_network(
        token_registry_abi=abi,
        token_registry_address=ctx.obj["deployed_contracts"][CONTRACT_TOKEN_NETWORK_REGISTRY],
        token_address=ctx.obj["deployed_contracts"][token_type],
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
    )


@main.command()
@click.option(
    "--rpc-provider", default="http://127.0.0.1:8545", help="Address of the Ethereum RPC provider"
)
@click.option(
    "--contracts-version",
    help="Contracts version to verify. Current version will be used by default.",
)
@click.pass_context
def verify(_: Any, rpc_provider: str, contracts_version: Optional[str]) -> None:
    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={"timeout": 60}))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    print("Web3 provider is", web3.providers[0])

    verifier = ContractVerifier(web3=web3, contracts_version=contracts_version)
    verifier.verify_deployed_contracts_in_filesystem()


if __name__ == "__main__":
    main()
