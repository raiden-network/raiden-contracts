import logging
from typing import Any, Callable

import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.tests.utils.constants import CONTRACT_DEPLOYER_ADDRESS

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def deploy_tester_contract(web3, contracts_manager, deploy_contract):
    """Returns a function that can be used to deploy a named contract,
    using conract manager to compile the bytecode and get the ABI"""

    def f(contract_name, args=None):
        json_contract = contracts_manager.get_contract(contract_name)
        contract = deploy_contract(
            web3, CONTRACT_DEPLOYER_ADDRESS, json_contract["abi"], json_contract["bin"], args
        )
        return contract

    return f


@pytest.fixture(scope="session")
def deploy_contract_txhash() -> Callable[..., Any]:
    """Returns a function that deploys a compiled contract, returning a txhash"""

    def fn(web3, deployer_address, abi, bytecode, args):
        if args is None:
            args = []
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        # Failure does not fire an exception.  Check the receipt for status.
        return contract.constructor(*args).transact({"from": deployer_address})

    return fn


@pytest.fixture(scope="session")
def deploy_contract(deploy_contract_txhash):
    """Returns a function that deploys a compiled contract"""

    def fn(web3, deployer_address, abi, bytecode, args):
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)
        txhash = deploy_contract_txhash(web3, deployer_address, abi, bytecode, args)
        contract_address = web3.eth.getTransactionReceipt(txhash).contractAddress
        web3.testing.mine(1)

        if web3.eth.getTransactionReceipt(txhash).status != 1:
            raise TransactionFailed("deployment failed")

        return contract(contract_address)

    return fn


@pytest.fixture
def deploy_tester_contract_txhash(web3, contracts_manager, deploy_contract_txhash):
    """Returns a function that can be used to deploy a named contract,
    but returning txhash only"""

    def f(contract_name, args=None):
        json_contract = contracts_manager.get_contract(contract_name)
        txhash = deploy_contract_txhash(
            web3, CONTRACT_DEPLOYER_ADDRESS, json_contract["abi"], json_contract["bin"], args
        )
        return txhash

    return f


@pytest.fixture
def utils_contract(deploy_tester_contract):
    """Deployed Utils contract"""
    return deploy_tester_contract("Utils")
