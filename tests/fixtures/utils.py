import pytest
from utils.logs import LogHandler

print_the_logs = False

raiden_contracts_version = '0.3.0'
MAX_UINT256 = 2 ** 256 - 1
MAX_UINT192 = 2 ** 192 - 1
MAX_UINT32 = 2 ** 32 - 1
fake_address = '0x03432'
empty_address = '0x0000000000000000000000000000000000000000'
passphrase = '0'


def fake_hex(size):
    return '0x' + ''.join(['02' for i in range(0, size)])


def fake_bytes(size):
    return bytearray.fromhex(fake_hex(size)[2:])


@pytest.fixture()
def owner_index():
    return 1


@pytest.fixture()
def owner(web3, owner_index):
    return web3.eth.accounts[owner_index]


@pytest.fixture()
def get_accounts(web3, owner_index, create_accounts):
    def get(number, index_start=None):
        if not index_start:
            index_start = owner_index + 1
        accounts_len = len(web3.eth.accounts)
        index_end = min(number + index_start, accounts_len)
        accounts = web3.eth.accounts[index_start:index_end]
        if number > len(accounts):
            accounts += create_accounts(number - len(accounts))
        return accounts
    return get


@pytest.fixture()
def create_accounts(web3):
    def get(number):
        new_accounts = []
        for i in range(0, number):
            new_account = web3.personal.newAccount(passphrase)
            amount = int(web3.eth.getBalance(web3.eth.accounts[0]) / 2 / number)
            web3.eth.sendTransaction({
                'from': web3.eth.accounts[0],
                'to': new_account,
                'value': amount
            })
            web3.personal.unlockAccount(new_account, passphrase)
            new_accounts.append(new_account)
        return new_accounts
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
def event_handler(chain, web3):
    def get(contract=None, address=None, abi=None):
        if contract:
            # Get contract factory name from contract instance
            # TODO is there an actual API for this??
            comp_target = contract.metadata['settings']['compilationTarget']
            name = comp_target[list(comp_target.keys())[0]]

            abi = chain.provider.get_base_contract_factory(name).abi
            address = contract.address

        if address and abi:
            return LogHandler(web3, address, abi)
        else:
            raise Exception('event_handler called without a contract instance')
    return get


@pytest.fixture
def txn_cost(web3, txnGas):
    def get(txn_hash):
        return txnGas(txn_hash) * web3.eth.gasPrice
    return get


@pytest.fixture
def txn_gas(chain):
    def get(txn_hash):
        receipt = chain.wait.for_receipt(txn_hash)
        return receipt['gasUsed']
    return get


@pytest.fixture
def print_gas(chain, txn_gas):
    def get(txn_hash, message=None, additional_gas=0):
        gas_used = txn_gas(txn_hash)
        if not message:
            message = txn_hash

        print('----------------------------------')
        print('GAS USED ' + message, gas_used + additional_gas)
        print('----------------------------------')
    return get


@pytest.fixture()
def get_block(chain):
    def get(txn_hash):
        receipt = chain.wait.for_receipt(txn_hash)
        return receipt['blockNumber']
    return get
