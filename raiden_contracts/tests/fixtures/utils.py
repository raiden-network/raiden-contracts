import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.utils.logs import LogHandler
from raiden_libs.utils import private_key_to_address
from .config import passphrase
from eth_utils import denoms, is_same_address


@pytest.fixture()
def owner_index():
    return 1


@pytest.fixture()
def owner(faucet_address):
    return faucet_address


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


@pytest.fixture
def create_account(web3, ethereum_tester, get_random_privkey):
    def get():
        privkey = get_random_privkey()
        address = private_key_to_address(privkey)
        ethereum_tester.add_account(privkey)
        for faucet in web3.eth.accounts[:10]:
            try:
                web3.eth.sendTransaction({
                    'from': faucet,
                    'to': address,
                    'value': 1 * denoms.finney,
                })
                break
            except TransactionFailed:
                continue
        return address
    return get


@pytest.fixture()
def get_accounts(create_account):
    def get(number):
        return [
            create_account()
            for x in range(number)
        ]

    return get


@pytest.fixture
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


@pytest.fixture
def create_contract(chain, owner):
    def get(contract_type, arguments, transaction=None):
        if not transaction:
            transaction = {}
        if 'from' not in transaction:
            transaction['from'] = owner

        deploy_txn_hash = contract_type.deploy(transaction=transaction, args=arguments)
        contract_address = chain.wait.for_contract_address(deploy_txn_hash)
        contract = contract_type(address=contract_address)
        return contract
    return get


@pytest.fixture()
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


@pytest.fixture
def print_gas(web3, txn_gas):
    def get(txn_hash, message=None, additional_gas=0):
        gas_used = txn_gas(txn_hash)
        if not message:
            message = txn_hash

        print('----------------------------------')
        print('GAS USED ' + message, gas_used + additional_gas)
        print('----------------------------------')
    return get


@pytest.fixture()
def get_block(web3):
    def get(txn_hash):
        receipt = web3.eth.getTransactionReceipt(txn_hash)
        return receipt['blockNumber']
    return get
