import logging
from typing import Callable, List, Optional

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_typing import HexAddress
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.utils.constants import CONTRACT_DEPLOYER_ADDRESS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def deploy_tester_contract(
    web3: Web3, contracts_manager: ContractManager, deploy_contract: Callable
) -> Callable:
    """Returns a function that can be used to deploy a named contract,
    using conract manager to compile the bytecode and get the ABI"""

    def f(contract_name: str, args: Optional[List] = None) -> Contract:
        json_contract = contracts_manager.get_contract(contract_name)
        contract = deploy_contract(
            web3, CONTRACT_DEPLOYER_ADDRESS, json_contract["abi"], json_contract["bin"], args
        )
        return contract

    return f


@pytest.fixture(scope="session")
def deploy_contract_txhash() -> Callable[..., str]:
    """Returns a function that deploys a compiled contract, returning a txhash"""

    def fn(
        web3: Web3, deployer_address: HexAddress, abi: List, bytecode: str, args: Optional[List]
    ) -> str:
        if args is None:
            args = []
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        # Failure does not fire an exception.  Check the receipt for status.
        return contract.constructor(*args).transact({"from": deployer_address})

    return fn


@pytest.fixture(scope="session")
def deploy_contract(deploy_contract_txhash: Callable) -> Callable:
    """Returns a function that deploys a compiled contract"""

    def fn(
        web3: Web3, deployer_address: HexAddress, abi: List, bytecode: str, args: List
    ) -> Contract:
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        txhash = deploy_contract_txhash(web3, deployer_address, abi, bytecode, args)
        contract_address = web3.eth.getTransactionReceipt(txhash).contractAddress
        web3.testing.mine(1)

        if web3.eth.getTransactionReceipt(txhash).status != 1:
            raise TransactionFailed("deployment failed")

        return contract(contract_address)

    return fn


@pytest.fixture
def deploy_tester_contract_txhash(
    web3: Web3, contracts_manager: ContractManager, deploy_contract_txhash: Callable
) -> Callable:
    """Returns a function that can be used to deploy a named contract,
    but returning txhash only"""

    def f(contract_name: str, args: Optional[List] = None) -> str:
        json_contract = contracts_manager.get_contract(contract_name)
        txhash = deploy_contract_txhash(
            web3, CONTRACT_DEPLOYER_ADDRESS, json_contract["abi"], json_contract["bin"], args
        )
        return txhash

    return f


@pytest.fixture
def utils_contract(deploy_tester_contract: Callable) -> Contract:
    """Deployed Utils contract"""
    return deploy_tester_contract("Utils")
