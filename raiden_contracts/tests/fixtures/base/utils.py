import json
from sys import argv
from typing import Callable, Dict, Iterable, List, Optional

import pytest
from eth_tester import EthereumTester
from eth_tester.exceptions import TransactionFailed
from eth_typing.evm import HexAddress
from eth_utils import is_same_address
from eth_utils.units import units
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.contract_manager import contracts_gas_path
from raiden_contracts.tests.utils import get_random_privkey
from raiden_contracts.utils.logs import LogHandler
from raiden_contracts.utils.signature import private_key_to_address


@pytest.fixture(scope="session")
def create_account(web3: Web3, ethereum_tester: EthereumTester) -> Callable:
    def get(privkey: Optional[str] = None) -> HexAddress:
        if not privkey:
            privkey = get_random_privkey()
        address = private_key_to_address(privkey)

        if not any((is_same_address(address, x) for x in ethereum_tester.get_accounts())):
            # account has not been added to ethereum_tester, yet
            ethereum_tester.add_account(privkey)

        for faucet in web3.eth.accounts[:10]:
            try:
                web3.eth.sendTransaction(
                    {"from": faucet, "to": address, "value": 1 * int(units["finney"])}
                )
                break
            except TransactionFailed:
                continue
        return address

    return get


@pytest.fixture(scope="session")
def get_accounts(create_account: Callable) -> Callable:
    def get(number: int, privkeys: Iterable = ()) -> List:
        privkeys = iter(privkeys)
        return [create_account(privkey=next(privkeys, None)) for x in range(number)]

    return get


@pytest.fixture(scope="session")
def create_service_account(
    create_account: Callable, service_registry: Contract, custom_token: Contract
) -> Callable:
    """Returns an address registered to ServiceRegistry"""

    def get() -> HexAddress:
        account = create_account()
        deposit = service_registry.functions.currentPrice().call()
        custom_token.functions.mint(deposit).call_and_transact({"from": account})
        custom_token.functions.approve(service_registry.address, deposit).call_and_transact(
            {"from": account}
        )
        service_registry.functions.deposit(deposit).call_and_transact({"from": account})
        assert service_registry.functions.hasValidRegistration(account).call()
        return account

    return get


@pytest.fixture(scope="session")
def get_private_key(ethereum_tester: EthereumTester) -> Callable:
    def get(account_address: HexAddress) -> str:
        keys = [
            key.to_hex()
            for key in ethereum_tester.backend.account_keys
            if is_same_address(key.public_key.to_address(), account_address)
        ]
        assert len(keys) == 1
        return keys[0]

    return get


@pytest.fixture(scope="session")
def event_handler(web3: Web3) -> Callable:
    def get(
        contract: Optional[Contract] = None,
        address: Optional[HexAddress] = None,
        abi: Optional[List] = None,
    ) -> LogHandler:
        if contract:
            abi = contract.abi
            address = contract.address

        if address and abi:
            return LogHandler(web3=web3, address=address, abi=abi)
        else:
            raise Exception("event_handler called without a contract instance")

    return get


@pytest.fixture
def txn_cost(web3: Web3, txn_gas: Callable) -> Callable:
    def get(txn_hash: str) -> int:
        return txn_gas(txn_hash) * web3.eth.gasPrice

    return get


@pytest.fixture
def txn_gas(web3: Web3) -> Callable:
    def get(txn_hash: str) -> int:
        receipt = web3.eth.getTransactionReceipt(txn_hash)
        return receipt["gasUsed"]

    return get


@pytest.fixture(scope="session")
def gas_measurement_results() -> Dict:
    results: Dict = {}
    return results


def sys_args_contain(searched: str) -> bool:
    """ Returns True if 'searched' appears in any of the command line arguments. """
    for arg in argv:
        if arg.find(searched) != -1:
            return True
    return False


@pytest.fixture
def print_gas(txn_gas: Callable, gas_measurement_results: Dict) -> Callable:
    def get(txn_hash: str, message: Optional[str] = None, additional_gas: int = 0) -> None:
        if not sys_args_contain("test_print_gas"):
            # If the command line arguments don't contain 'test_print_gas', do nothing
            return

        gas_used = txn_gas(txn_hash)
        if not message:
            message = txn_hash

        print("----------------------------------")
        print("GAS USED " + message, gas_used + additional_gas)
        print("----------------------------------")
        gas_measurement_results[message] = gas_used + additional_gas
        with contracts_gas_path().open(mode="w") as target_file:
            target_file.write(json.dumps(gas_measurement_results, sort_keys=True, indent=4))

    return get


@pytest.fixture()
def get_block(web3: Web3) -> Callable:
    def get(txn_hash: str) -> int:
        receipt = web3.eth.getTransactionReceipt(txn_hash)
        return receipt["blockNumber"]

    return get
