'''
A simple Python script to deploy compiled contracts.
'''
import click
import json
from web3 import Web3, HTTPProvider
from eth_utils import (
    is_address,
    to_checksum_address,
)
from raiden_contracts.utils.utils import (
    check_succesful_tx
)


@click.command()
@click.option(
    '--rpc-provider',
    default="http://127.0.0.1:8545",
    help='Address of the Ethereum RPC provider'
)
@click.option(
    '--json',
    default="build/contracts.json",
    help='Path to compiled contracts data'
)
@click.option(
    '--owner',
    help='Contracts owner, default: web3.eth.accounts[0]'
)
@click.option(
    '--supply',
    default=10000000,
    help='Token contract supply (number of total issued tokens).'
)
@click.option(
    '--token-name',
    default='CustomToken',
    help='Token contract name.'
)
@click.option(
    '--token-decimals',
    default=18,
    help='Token contract number of decimals.'
)
@click.option(
    '--token-symbol',
    default='TKN',
    help='Token contract symbol.'
)
@click.option(
    '--token-address',
    help='Already deployed token address.'
)
@click.option(
    '--wait',
    default=300,
    help='Token contract number of decimals.'
)
@click.option(
    '--gas-price',
    default=0,
    help='Token contract number of decimals.'
)
def main(**kwargs):
    rpc_provider = kwargs['rpc_provider']
    json_file = kwargs['json']
    owner = kwargs['owner']
    supply = kwargs['supply']
    token_name = kwargs['token_name']
    token_decimals = kwargs['token_decimals']
    token_symbol = kwargs['token_symbol']
    token_address = kwargs['token_address']
    supply *= 10**(token_decimals)
    txn_wait = kwargs['wait']
    gas_price = kwargs['gas_price']

    print('''Make sure chain is running, you can connect to it and it is synced,
          or you'll get timeout''')

    web3 = Web3(HTTPProvider(rpc_provider, request_kwargs={'timeout': 60}))
    print('Web3 provider is', web3.providers[0])

    owner = owner or web3.eth.accounts[0]
    assert owner and is_address(owner), 'Invalid owner provided.'
    owner = to_checksum_address(owner)
    print('Owner is', owner)
    assert web3.eth.getBalance(owner) > 0, 'Account with insuficient funds.'

    transaction={'from': owner}
    if gas_price == 0:
        transaction['gasPrice'] = gas_price

    with open(json_file) as json_data:
        contracts_compiled_data = json.load(json_data)

        if not token_address:
            token_address = deploy_contract(web3, contracts_compiled_data, 'CustomToken', transaction, txn_wait, [supply, token_decimals, token_name, token_symbol])

        assert token_address and is_address(token_address)
        token_address = to_checksum_address(token_address)

        secret_registry_address = deploy_contract(web3, contracts_compiled_data, 'SecretRegistry', transaction, txn_wait)

        token_network_registry_address = deploy_contract(web3, contracts_compiled_data, 'TokenNetworksRegistry', transaction, txn_wait, [secret_registry_address, int(web3.version.network)])

        token_network_registry = instantiate_contract(web3, contracts_compiled_data, 'TokenNetworksRegistry', token_network_registry_address)

        txhash = token_network_registry.transact(transaction).createERC20TokenNetwork(token_address)
        receipt = check_succesful_tx(web3, txhash, txn_wait)

        print('TokenNetwork address: {0}. Gas used: {1}'.format(
            token_network_registry.call().token_to_token_networks(token_address),
            receipt['gasUsed'])
        )


def instantiate_contract(web3, contracts_compiled_data, contract_name, contract_address):
    contract_interface = contracts_compiled_data[contract_name]

    contract = web3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bytecode'], address=contract_address)

    return contract

def deploy_contract(web3, contracts_compiled_data, contract_name, transaction, txn_wait=200, args=[]):
    contract_interface = contracts_compiled_data[contract_name]

    # Instantiate and deploy contract
    contract = web3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bytecode'])

    # Get transaction hash from deployed contract
    txhash = contract.deploy(transaction=transaction, args=args)

    # Get tx receipt to get contract address
    receipt = check_succesful_tx(web3, txhash, txn_wait)
    print('{0} address: {1}. Gas used: {2}'.format(contract_name, receipt['contractAddress'], receipt['gasUsed']))
    return receipt['contractAddress']


if __name__ == '__main__':
    main()
