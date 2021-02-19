import logging
from typing import Any, Callable, Dict, Tuple

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_typing import HexAddress
from solcx import link_code
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.tests.utils.constants import DEPLOYER_ADDRESS

log = logging.getLogger(__name__)


def deploy_contract_txhash(
    web3: Web3,
    contracts_manager: ContractManager,
    deployer_address: HexAddress,
    contract_name: str,
    libs: Dict = None,
    **kwargs: Any,
) -> Tuple[HexAddress, Contract]:
    json_contract = contracts_manager.get_contract(contract_name)
    abi = json_contract["abi"]
    bytecode = json_contract["bin"]
    bytecode_runtime = None

    if isinstance(libs, dict) and len(libs.keys()) > 0:
        bytecode = link_code(bytecode, libs)
        bytecode_runtime = link_code(json_contract["bin-runtime"], libs)

    if bytecode_runtime is not None:
        contract = web3.eth.contract(abi=abi, bytecode=bytecode, bytecode_runtime=bytecode_runtime)
    else:
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)

    mine_blocks(web3, 3)
    # Failure does not fire an exception. Check the receipt for status.
    txhash = contract.constructor(**kwargs).transact({"from": deployer_address})
    mine_blocks(web3, 1)

    receipt = web3.eth.getTransactionReceipt(txhash)
    if receipt["status"] != 1:
        raise TransactionFailed("deployment failed")

    return txhash, contract(receipt["contractAddress"])


@pytest.fixture
def deploy_tester_contract_txhash(web3: Web3, contracts_manager: ContractManager) -> Callable:
    """Returns a function that can be used to deploy a named contract,
    but returning txhash only"""

    def f(
        contract_name: str,
        deployer_address: HexAddress = DEPLOYER_ADDRESS,
        libs: Dict = None,
        **kwargs: Any,
    ) -> HexAddress:
        txhash, _ = deploy_contract_txhash(
            web3,
            contracts_manager,
            deployer_address,
            contract_name,
            libs,
            **kwargs,
        )
        return txhash

    return f


@pytest.fixture(scope="session")
def deploy_tester_contract(web3: Web3, contracts_manager: ContractManager) -> Callable:
    """Returns a function that can be used to deploy a named contract,
    using contract manager to compile the bytecode and get the ABI"""

    def f(
        contract_name: str,
        libs: Dict = None,
        deployer_address: HexAddress = DEPLOYER_ADDRESS,
        **kwargs: Any,
    ) -> Contract:
        _, contract = deploy_contract_txhash(
            web3,
            contracts_manager,
            deployer_address,
            contract_name,
            libs,
            **kwargs,
        )
        return contract

    return f
