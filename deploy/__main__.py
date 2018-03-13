'''
A simple Python script to deploy contracts.
'''
import click
from populus import Project
from eth_utils import (
    is_address,
    to_checksum_address,
)
from utils.utils import (
    check_succesful_tx
)


@click.command()
@click.option(
    '--chain',
    default='ropsten',
    help='Chain to deploy on: kovan | ropsten | rinkeby | tester | privtest'
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
def main(**kwargs):
    project = Project()

    chain_name = kwargs['chain']
    owner = kwargs['owner']
    supply = kwargs['supply']
    token_name = kwargs['token_name']
    token_decimals = kwargs['token_decimals']
    token_symbol = kwargs['token_symbol']
    token_address = kwargs['token_address']
    supply *= 10**(token_decimals)
    txn_wait = 300

    print('''Make sure {} chain is running, you can connect to it and it is synced,
          or you'll get timeout'''.format(chain_name))


    with project.get_chain(chain_name) as chain:
        web3 = chain.web3
        print('Web3 provider is', web3.providers[0])

        owner = owner or web3.eth.accounts[0]
        assert owner and is_address(owner), 'Invalid owner provided.'
        owner = to_checksum_address(owner)
        print('Owner is', owner)
        assert web3.eth.getBalance(owner) > 0, 'Account with insuficient funds.'

        def deploy_contract(contract_name, args=[]):
            contract = chain.provider.get_contract_factory(contract_name)
            txhash = contract.deploy(
                args=args,
                transaction={'from': owner}
            )
            receipt = check_succesful_tx(chain.web3, txhash, txn_wait)
            return receipt['contractAddress']

        token = chain.provider.get_contract_factory('CustomToken')

        if not token_address:
            txhash = token.deploy(
                args=[supply, token_decimals, token_name, token_symbol],
                transaction={'from': owner}
            )
            receipt = check_succesful_tx(chain.web3, txhash, txn_wait)
            token_address = receipt['contractAddress']

        assert token_address and is_address(token_address)
        token_address = to_checksum_address(token_address)
        print(token_name, 'address is', token_address)

        secret_registry_address = deploy_contract('SecretRegistry')
        print('SecretRegistry address:', secret_registry_address)

        token_network_registry_address = deploy_contract('TokenNetworkRegistry', [secret_registry_address])
        print('TokenNetworkRegistry address:', token_network_registry_address)

        token_network_address = deploy_contract('TokenNetwork', [token_address, secret_registry_address])
        print('TokenNetwork address:', token_network_address)


if __name__ == '__main__':
    main()
