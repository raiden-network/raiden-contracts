import logging
from typing import Callable, Dict, List

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_typing import HexAddress
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.tests.utils.constants import DEPLOYER_ADDRESS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def deploy_tester_contract(
    web3: Web3, contracts_manager: ContractManager, deploy_contract: Callable
) -> Callable:
    """Returns a function that can be used to deploy a named contract,
    using conract manager to compile the bytecode and get the ABI"""

    def f(contract_name: str, **kwargs: Dict) -> Contract:
        json_contract = contracts_manager.get_contract(contract_name)
        contract = deploy_contract(
            web3, DEPLOYER_ADDRESS, json_contract["abi"], json_contract["bin"], **kwargs
        )
        return contract

    return f


@pytest.fixture(scope="session")
def deploy_contract_txhash() -> Callable[..., str]:
    """Returns a function that deploys a compiled contract, returning a txhash"""

    def fn(
        web3: Web3, deployer_address: HexAddress, abi: List, bytecode: str, **kwargs: Dict
    ) -> str:
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        # Failure does not fire an exception.  Check the receipt for status.
        return contract.constructor(**kwargs).transact({"from": deployer_address})

    return fn


@pytest.fixture(scope="session")
def deploy_contract(deploy_contract_txhash: Callable) -> Callable:
    """Returns a function that deploys a compiled contract"""

    def fn(
        web3: Web3, deployer_address: HexAddress, abi: List, bytecode: str, **kwargs: Dict
    ) -> Contract:
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        txhash = deploy_contract_txhash(web3, deployer_address, abi, bytecode, **kwargs)
        contract_address = web3.eth.getTransactionReceipt(txhash)["contractAddress"]
        mine_blocks(web3, 1)

        if web3.eth.getTransactionReceipt(txhash)["status"] != 1:
            raise TransactionFailed("deployment failed")

        return contract(contract_address)

    return fn


@pytest.fixture
def deploy_tester_contract_txhash(
    web3: Web3, contracts_manager: ContractManager, deploy_contract_txhash: Callable
) -> Callable:
    """Returns a function that can be used to deploy a named contract,
    but returning txhash only"""

    def f(contract_name: str, **kwargs: Dict) -> str:
        json_contract = contracts_manager.get_contract(contract_name)
        txhash = deploy_contract_txhash(
            web3, DEPLOYER_ADDRESS, json_contract["abi"], json_contract["bin"], **kwargs
        )
        return txhash

    return f


@pytest.fixture
def utils_contract(deploy_tester_contract: Callable) -> Contract:
    """Deployed Utils contract"""
    return deploy_tester_contract("Utils")
