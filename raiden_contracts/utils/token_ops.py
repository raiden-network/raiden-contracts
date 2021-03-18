import functools
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import click
import requests
from eth_typing import URI, ChecksumAddress
from eth_utils import to_checksum_address
from hexbytes import HexBytes
from web3 import HTTPProvider, Web3
from web3.middleware import construct_sign_and_send_raw_middleware, geth_poa_middleware
from web3.types import TxReceipt, Wei

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN
from raiden_contracts.contract_manager import ContractManager, contracts_precompiled_path
from raiden_contracts.utils.private_key import get_private_key
from raiden_contracts.utils.signature import private_key_to_address
from raiden_contracts.utils.transaction import check_successful_tx


class TokenOperations:
    def __init__(
        self, rpc_url: URI, private_key: Path, password: Optional[Path] = None, wait: int = 10
    ):
        self.web3 = Web3(HTTPProvider(rpc_url))
        self.private_key = get_private_key(private_key, password)
        assert self.private_key is not None
        self.owner = private_key_to_address(self.private_key)
        self.wait = wait
        self.web3.middleware_onion.add(construct_sign_and_send_raw_middleware(self.private_key))
        self.web3.eth.default_account = self.owner

        self.web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    def is_valid_contract(self, token_address: ChecksumAddress) -> bool:
        return self.web3.eth.get_code(token_address, "latest") != HexBytes("")

    def mint_tokens(self, token_address: ChecksumAddress, amount: int) -> TxReceipt:
        token_address = to_checksum_address(token_address)
        assert self.is_valid_contract(
            token_address
        ), "The custom token contract does not seem to exist on this address"
        token_contract = ContractManager(contracts_precompiled_path()).get_contract(
            CONTRACT_CUSTOM_TOKEN
        )
        token_proxy = self.web3.eth.contract(address=token_address, abi=token_contract["abi"])
        txhash = token_proxy.functions.mint(amount).transact({"from": self.owner})
        receipt, _ = check_successful_tx(web3=self.web3, txid=txhash, timeout=self.wait)
        return receipt

    def get_weth(self, token_address: ChecksumAddress, amount: int) -> TxReceipt:
        token_address = to_checksum_address(token_address)
        assert (
            self.web3.eth.get_balance(self.owner) > amount
        ), "Not sufficient ether to make a deposit to WETH contract"
        assert self.is_valid_contract(
            token_address
        ), "The WETH token does not exist on this contract"
        result = requests.get(
            "http://api.etherscan.io/api?module=contract&action=getabi&"
            "address=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        )
        weth_abi = result.json()["result"]
        weth_proxy = self.web3.eth.contract(address=token_address, abi=weth_abi)
        assert weth_proxy.functions.symbol().call() == "WETH", "This contract is not a WETH token"
        txhash = weth_proxy.functions.deposit().transact(
            {"from": self.owner, "value": Wei(amount)}
        )
        receipt, _ = check_successful_tx(web3=self.web3, txid=txhash, timeout=self.wait)
        return receipt

    # Could be used for both custom token as well as WETH contracts
    def transfer_tokens(self, token_address: ChecksumAddress, dest: str, amount: int) -> TxReceipt:
        token_address = to_checksum_address(token_address)
        dest = to_checksum_address(dest)
        assert self.is_valid_contract(
            token_address
        ), "The token contract does not seem to exist on this address"
        token_contract = ContractManager(contracts_precompiled_path()).get_contract(
            CONTRACT_CUSTOM_TOKEN
        )
        token_proxy = self.web3.eth.contract(address=token_address, abi=token_contract["abi"])
        assert (
            token_proxy.functions.balanceOf(self.owner).call() >= amount
        ), "Not enough token balances"
        txhash = token_proxy.functions.transfer(dest, amount).transact({"from": self.owner})
        receipt, _ = check_successful_tx(web3=self.web3, txid=txhash, timeout=self.wait)
        return receipt

    def get_balance(self, token_address: ChecksumAddress, address: str) -> int:
        token_address = to_checksum_address(token_address)
        address = to_checksum_address(address)
        assert self.is_valid_contract(
            token_address
        ), "The Token Contract does not seem to exist on this address"
        token_contract = ContractManager(contracts_precompiled_path()).get_contract(
            CONTRACT_CUSTOM_TOKEN
        )
        token_proxy = self.web3.eth.contract(address=token_address, abi=token_contract["abi"])
        return token_proxy.functions.balanceOf(address).call()


def common_options(func: Callable) -> Callable:
    """A decorator that combines commonly appearing @click.option decorators."""

    @click.option(
        "--private-key", required=True, help="Path to a private key store.", type=click.STRING
    )
    @click.option("--password", help="password file for the keystore json file", type=click.STRING)
    @click.option(
        "--rpc-url",
        default="http://127.0.0.1:8545",
        help="Address of the Ethereum RPC provider",
        type=click.STRING,
    )
    @click.option(
        "--token-address", required=True, help="Address of the token contract", type=click.STRING
    )
    @click.option(
        "--amount", required=True, help="Amount to mint/deposit/transfer", type=click.INT
    )
    @click.option("--wait", default=300, help="Max tx wait time in s.", type=click.INT)
    @functools.wraps(func)
    def wrapper(*args: List, **kwargs: Dict) -> Any:
        return func(*args, **kwargs)

    return wrapper


@click.group()
def cli() -> None:
    pass


@cli.command()
@common_options
def mint(
    private_key: str,
    password: str,
    rpc_url: URI,
    token_address: ChecksumAddress,
    amount: int,
    wait: int,
) -> None:
    password_file = Path(password) if password else None
    token_ops = TokenOperations(rpc_url, Path(private_key), password_file, wait)
    receipt = token_ops.mint_tokens(token_address, amount)
    print(f"Minting tokens for {token_ops.owner}")
    print(receipt)
    balance = token_ops.get_balance(token_address, token_ops.owner)
    print(f"Balance of the {token_ops.owner} :  {balance}")


@cli.command()
@common_options
def weth(
    private_key: str,
    password: Optional[str],
    rpc_url: URI,
    token_address: ChecksumAddress,
    amount: int,
    wait: int,
) -> None:
    password_path = Path(password) if password else None
    token_ops = TokenOperations(rpc_url, Path(private_key), password_path, wait)
    receipt = token_ops.get_weth(token_address, amount)
    print(f"Getting WETH tokens for {token_ops.owner}")
    print(receipt)
    balance = token_ops.get_balance(token_address, token_ops.owner)
    print(f"Balance of the {token_ops.owner} : {balance}")


@cli.command()
@common_options
@click.option("--destination", help="Address of payee account", type=click.STRING)
def transfer(
    private_key: str,
    password: str,
    rpc_url: URI,
    token_address: ChecksumAddress,
    amount: int,
    wait: int,
    destination: str,
) -> None:
    password_path = Path(password) if password else None
    token_ops = TokenOperations(rpc_url, Path(private_key), password_path, wait)
    receipt = token_ops.transfer_tokens(token_address, destination, amount)
    print(f"Transferring tokens to {destination}")
    print(receipt)
    balance = token_ops.get_balance(token_address, token_ops.owner)
    print(f"Balance of the {token_ops.owner} : {balance}")


@cli.command()
@click.option(
    "--rpc-url",
    default="http://127.0.0.1:8545",
    help="Address of the Ethereum RPC provider",
    type=click.STRING,
)
@click.option(
    "--token-address",
    required=True,
    help="Address of the token contract",
    type=click.STRING,
)
@click.option("--address", help="Address of account to get Balance", type=click.STRING)
def balance(rpc_url: URI, token_address: str, address: str) -> None:
    token_address = to_checksum_address(token_address)
    address = to_checksum_address(address)
    web3 = Web3(HTTPProvider(rpc_url))
    token_contract = ContractManager(contracts_precompiled_path()).get_contract(
        CONTRACT_CUSTOM_TOKEN
    )
    token_proxy = web3.eth.contract(address=token_address, abi=token_contract["abi"])
    balance = token_proxy.functions.balanceOf(address).call()
    print(f"Balance of the {address} : {balance}")


if __name__ == "__main__":
    cli()
