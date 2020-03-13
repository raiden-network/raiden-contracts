from typing import Any, List, Optional

from coincurve import PrivateKey
from eth_tester import EthereumTester
from eth_typing.evm import ChecksumAddress
from hexbytes import HexBytes
from web3 import Web3
from web3.contract import Contract, ContractFunction
from web3.providers.eth_tester import EthereumTesterProvider
from web3.types import TxParams

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_TOKEN_NETWORK
from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.utils.constants import FAUCET_ALLOWANCE
from raiden_contracts.utils.signature import private_key_to_address


def get_web3(eth_tester: EthereumTester, deployer_key: PrivateKey) -> Web3:
    """Returns an initialized Web3 instance"""
    provider = EthereumTesterProvider(eth_tester)
    web3 = Web3(provider)

    # add faucet account to tester
    eth_tester.add_account(deployer_key.to_hex())

    # make faucet rich
    eth_tester.send_transaction(
        {
            "from": eth_tester.get_accounts()[0],
            "to": private_key_to_address(deployer_key.to_hex()),
            "gas": 21000,
            "value": FAUCET_ALLOWANCE,
        }
    )

    return web3


def deploy_contract(
    web3: Web3,
    contracts_manager: ContractManager,
    contract_name: str,
    deployer_key: PrivateKey,
    args: List[Any],
) -> Contract:
    deployer_address = private_key_to_address(deployer_key.to_hex())
    json_contract = contracts_manager.get_contract(contract_name)
    contract = web3.eth.contract(abi=json_contract["abi"], bytecode=json_contract["bin"])
    tx_hash = contract.constructor(*args).transact(TxParams({"from": deployer_address}))
    contract_address = web3.eth.getTransactionReceipt(tx_hash)["contractAddress"]

    return contract(contract_address)


def deploy_custom_token(
    web3: Web3, deployer_key: PrivateKey, contract_manager: ContractManager
) -> Contract:
    return deploy_contract(
        web3=web3,
        contracts_manager=contract_manager,
        contract_name=CONTRACT_CUSTOM_TOKEN,
        deployer_key=deployer_key,
        args=[10 ** 26, 18, CONTRACT_CUSTOM_TOKEN, "TKN"],
    )


def get_token_network(
    web3: Web3, address: ChecksumAddress, contracts_manager: ContractManager
) -> Contract:
    json_contract = contracts_manager.get_contract(CONTRACT_TOKEN_NETWORK)

    return web3.eth.contract(abi=json_contract["abi"], address=address)


def call_and_transact(
    contract_function: ContractFunction, transaction_params: Optional[TxParams] = None,
) -> HexBytes:
    """ Executes contract_function.{call, transaction}(transaction_params) and returns txhash """
    # First 'call' might raise an exception
    contract_function.call(transaction_params)
    return contract_function.transact(transaction_params)
