import logging
from typing import Any, Callable, Tuple

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_typing import HexAddress
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
    **kwargs: Any,
) -> Tuple[HexAddress, Contract]:
    json_contract = contracts_manager.get_contract(contract_name)
    abi = json_contract["abi"]
    bytecode = json_contract["bin"]
    bytecode_runtime = None

    if bytecode_runtime is not None:
        contract = web3.eth.contract(abi=abi, bytecode=bytecode, bytecode_runtime=bytecode_runtime)
    else:
        contract = web3.eth.contract(abi=abi, bytecode=bytecode)

    mine_blocks(web3, 3)
    # Failure does not fire an exception. Check the receipt for status.
    txhash = contract.constructor(**kwargs).transact({"from": deployer_address})
    mine_blocks(web3, 1)

    receipt = web3.eth.get_transaction_receipt(txhash)
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
        **kwargs: Any,
    ) -> HexAddress:
        txhash, _ = deploy_contract_txhash(
            web3,
            contracts_manager,
            deployer_address,
            contract_name,
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
        deployer_address: HexAddress = DEPLOYER_ADDRESS,
        **kwargs: Any,
    ) -> Contract:
        _, contract = deploy_contract_txhash(
            web3,
            contracts_manager,
            deployer_address,
            contract_name,
            **kwargs,
        )
        return contract

    return f
