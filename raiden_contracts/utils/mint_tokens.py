#!/usr/bin/env python
import click
from eth_utils import encode_hex
from web3 import HTTPProvider, Web3
from web3.middleware import construct_sign_and_send_raw_middleware

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN
from raiden_contracts.contract_manager import ContractManager, contracts_precompiled_path
from raiden_contracts.utils.private_key import get_private_key
from raiden_contracts.utils.signature import private_key_to_address

WEI_TO_ETH = 10 ** 18


@click.command()
@click.option(
    "--rpc-url", help="Ethereum client rpc url", default="http://127.0.0.1:8545", required=True
)
@click.option("--private-key", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--token-address", help="address of the token contract", required=True)
@click.option("--amount", help="Amount of tokens to mint", required=True, type=click.INT)
def main(rpc_url, private_key, token_address, amount):
    web3 = Web3(HTTPProvider(rpc_url))
    private_key = get_private_key(private_key)
    assert private_key is not None
    owner = private_key_to_address(private_key)
    web3.middleware_stack.add(construct_sign_and_send_raw_middleware(private_key))
    token_code = web3.eth.getCode(token_address, "latest")
    assert token_code != b""
    token_contract = ContractManager(contracts_precompiled_path()).get_contract(
        CONTRACT_CUSTOM_TOKEN
    )
    token_proxy = web3.eth.contract(address=token_address, abi=token_contract["abi"])
    tx_hash = token_proxy.functions.mint(amount).transact({"from": owner})
    print(f"Minting tokens for address {owner}")
    print(f"Transaction hash {encode_hex(tx_hash)}")
    balance = token_proxy.functions.balanceOf(owner).call()
    print(f"Balance of {owner}: {balance}")


if __name__ == "__main__":
    main()
