import json
from sys import argv
from typing import Dict

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_utils import is_same_address
from eth_utils.units import units

from raiden_contracts.contract_manager import contracts_gas_path
from raiden_contracts.tests.utils import get_random_privkey
from raiden_contracts.utils.logs import LogHandler
from raiden_contracts.utils.signature import private_key_to_address


@pytest.fixture(scope="session")
def create_account(web3, ethereum_tester):
    def get(privkey=None):
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
def get_accounts(create_account):
    def get(number, privkeys=()):
        privkeys = iter(privkeys)
        return [create_account(privkey=next(privkeys, None)) for x in range(number)]

    return get


@pytest.fixture(scope="session")
def get_private_key(ethereum_tester):
    def get(account_address):
        keys = [
            key.to_hex()
            for key in ethereum_tester.backend.account_keys
            if is_same_address(key.public_key.to_address(), account_address)
        ]
        assert len(keys) == 1
        return keys[0]

    return get


@pytest.fixture(scope="session")
def event_handler(web3):
    def get(contract=None, address=None, abi=None):
        if contract:
            abi = contract.abi
            address = contract.address

        if address and abi:
            return LogHandler(web3=web3, address=address, abi=abi)
        else:
            raise Exception("event_handler called without a contract instance")

    return get


@pytest.fixture
def txn_cost(web3, txn_gas):
    def get(txn_hash):
        return txn_gas(txn_hash) * web3.eth.gasPrice

    return get


@pytest.fixture
def txn_gas(web3):
    def get(txn_hash):
        receipt = web3.eth.getTransactionReceipt(txn_hash)
        return receipt["gasUsed"]

    return get


@pytest.fixture(scope="session")
def gas_measurement_results():
    results: Dict = {}
    return results


def sys_args_contain(searched: str) -> bool:
    """ Returns True if 'searched' appears in any of the command line arguments. """
    for arg in argv:
        if arg.find(searched) != -1:
            return True
    return False


@pytest.fixture
def print_gas(txn_gas, gas_measurement_results):
    def get(txn_hash, message=None, additional_gas=0):
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
def get_block(web3):
    def get(txn_hash):
        receipt = web3.eth.getTransactionReceipt(txn_hash)
        return receipt["blockNumber"]

    return get
