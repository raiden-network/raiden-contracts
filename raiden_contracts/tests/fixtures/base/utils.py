import json
from typing import Dict

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_utils import denoms, is_same_address

from raiden_contracts.contract_manager import contracts_gas_path
from raiden_contracts.tests.utils import get_random_privkey
from raiden_contracts.tests.utils.constants import passphrase
from raiden_contracts.utils.logs import LogHandler
from raiden_contracts.utils.signature import private_key_to_address


@pytest.fixture()
def create_accounts(web3):
    def get(number):
        new_accounts = []
        for _ in range(0, number):
            new_account = web3.personal.newAccount(passphrase)
            amount = int(web3.eth.getBalance(web3.eth.accounts[0]) / 2 / number)
            web3.eth.sendTransaction({
                'from': web3.eth.accounts[0],
                'to': new_account,
                'value': amount,
            })
            web3.personal.unlockAccount(new_account, passphrase)
            new_accounts.append(new_account)
        return new_accounts
    return get


@pytest.fixture(scope='session')
def create_account(web3, ethereum_tester):
    def get():
        privkey = get_random_privkey()
        address = private_key_to_address(privkey)
        ethereum_tester.add_account(privkey)
        for faucet in web3.eth.accounts[:10]:
            try:
                web3.eth.sendTransaction({
                    'from': faucet,
                    'to': address,
                    'value': 1 * denoms.finney,  # pylint: disable=E1101
                })
                break
            except TransactionFailed:
                continue
        return address
    return get


@pytest.fixture(scope='session')
def get_accounts(create_account):
    def get(number):
        return [
            create_account()
            for x in range(number)
        ]

    return get


@pytest.fixture(scope='session')
def get_private_key(web3, ethereum_tester):
    def get(account_address):
        keys = [
            key.to_hex() for key in ethereum_tester.backend.account_keys
            if is_same_address(
                key.public_key.to_address(),
                account_address,
            )
        ]
        assert len(keys) == 1
        return keys[0]
    return get


@pytest.fixture(scope='session')
def event_handler(contracts_manager, web3):
    def get(contract=None, address=None, abi=None):
        if contract:
            abi = contract.abi
            address = contract.address

        if address and abi:
            return LogHandler(web3, address, abi)
        else:
            raise Exception('event_handler called without a contract instance')
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
        return receipt['gasUsed']
    return get


@pytest.fixture(scope='session')
def gas_measurement_results():
    results: Dict = {}
    return results


@pytest.fixture
def print_gas(web3, txn_gas, gas_measurement_results):
    def get(txn_hash, message=None, additional_gas=0):
        gas_used = txn_gas(txn_hash)
        if not message:
            message = txn_hash

        print('----------------------------------')
        print('GAS USED ' + message, gas_used + additional_gas)
        print('----------------------------------')
        gas_measurement_results[message] = gas_used + additional_gas
        with contracts_gas_path().open(mode='w') as target_file:
            target_file.write(json.dumps(
                gas_measurement_results,
                sort_keys=True,
                indent=4,
            ))
    return get


@pytest.fixture()
def get_block(web3):
    def get(txn_hash):
        receipt = web3.eth.getTransactionReceipt(txn_hash)
        return receipt['blockNumber']
    return get
