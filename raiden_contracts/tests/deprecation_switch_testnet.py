import click
from logging import getLogger
from eth_utils import encode_hex

from raiden_libs.private_contract import PrivateContract

from raiden_contracts.utils.utils import check_succesful_tx
from raiden_contracts.deploy.__main__ import (
    setup_ctx,
    deploy_raiden_contracts,
    deploy_token_contract,
    register_token_network,
)
from raiden_contracts.constants import (
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_TOKEN_NETWORK,
    MAX_ETH_CHANNEL_PARTICIPANT,
    DEPLOY_SETTLE_TIMEOUT_MIN,
)


log = getLogger(__name__)


@click.command()
@click.option(
    '--private-key',
    required=True,
    help='Path to a private key store.',
)
@click.option(
    '--rpc-provider',
    default='http://127.0.0.1:8545',
    help='Address of the Ethereum RPC provider',
)
@click.option(
    '--wait',
    default=300,
    help='Max tx wait time in s.',
)
@click.option(
    '--gas-price',
    default=5,
    type=int,
    help='Gas price to use in gwei',
)
@click.option(
    '--gas-limit',
    default=5_500_000,
)
@click.pass_context
def deprecation_test(
    ctx,
    private_key,
    rpc_provider,
    wait,
    gas_price,
    gas_limit,
):
    setup_ctx(ctx, private_key, rpc_provider, wait, gas_price, gas_limit)
    deployer = ctx.obj['deployer']

    # We deploy the Raiden Network contracts and register a token network
    token_amount = MAX_ETH_CHANNEL_PARTICIPANT * 6
    (
        token_network_registry,
        token_network,
        token_contract,
    ) = deprecation_test_setup(deployer, token_amount)

    log.info('Checking that channels can be opened and deposits can be made.')

    # Check that we can open channels and deposit on behalf of A and B
    # Some arbitrary Ethereum addresses
    A = '0x6AA63296FA94975017244769F00F0c64DB7d7115'
    B = '0xc9a4fad99B6d7D3e48D18d2585470cd8f27FA61e'
    channel_identifier = open_and_deposit(A, B, token_network, deployer)
    log.info('Seding transaction to activate the deprecation switch.')

    # Activate deprecation switch
    txhash = token_network.functions.deprecate().transact(
        deployer.transaction,
        private_key=deployer.private_key,
    )
    log.debug(f'Deprecation txHash={encode_hex(txhash)}')
    check_succesful_tx(deployer.web3, txhash, deployer.wait)
    assert token_network.functions.safety_deprecation_switch().call() is True

    log.info('Checking that channels cannot be opened anymore and no more deposits are allowed.')

    # Check that we cannot open more channels or deposit
    C = '0x5a23cedB607684118ccf7906dF3e24Efd2964719'
    D = '0x3827B9cDc68f061aa614F1b97E23664ef3b9220A'
    open_and_deposit(C, D, token_network, deployer, channel_identifier, False)

    log.info('Deprecation switch test OK.')


def deprecation_test_setup(deployer, token_amount):
    deployed_contracts = deploy_raiden_contracts(deployer)['contracts']

    token_network_registry_abi = deployer.contract_manager.get_contract_abi(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
    )
    token_network_registry = deployer.web3.eth.contract(
        abi=token_network_registry_abi,
        address=deployed_contracts[CONTRACT_TOKEN_NETWORK_REGISTRY]['address'],
    )
    token_network_registry = PrivateContract(token_network_registry)

    token_decimals = 18
    multiplier = 10 ** token_decimals
    token_supply = 10 ** 6 * multiplier
    token_amount = int(token_amount * multiplier)

    deployed_token = deploy_token_contract(
        deployer,
        token_supply,
        token_decimals,
        'TestToken',
        'TTT',
        CONTRACT_CUSTOM_TOKEN,
    )
    token_address = deployed_token[CONTRACT_CUSTOM_TOKEN]
    token_abi = deployer.contract_manager.get_contract_abi(CONTRACT_CUSTOM_TOKEN)
    token_contract = deployer.web3.eth.contract(
        abi=token_abi,
        address=token_address,
    )
    token_contract = PrivateContract(token_contract)

    # Mint some tokens for the owner
    txhash = token_contract.functions.mint(token_amount).transact(
        deployer.transaction,
        private_key=deployer.private_key,
    )

    log.debug(f'Minting tokens txHash={encode_hex(txhash)}')
    check_succesful_tx(deployer.web3, txhash, deployer.wait)
    assert token_contract.functions.balanceOf(deployer.owner).call() >= token_amount

    abi = deployer.contract_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK_REGISTRY)
    token_network_address = register_token_network(
        web3=deployer.web3,
        private_key=deployer.private_key,
        token_registry_abi=abi,
        token_registry_address=deployed_contracts[CONTRACT_TOKEN_NETWORK_REGISTRY]['address'],
        token_address=token_address,
        wait=deployer.wait,
    )

    token_network_abi = deployer.contract_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK)
    token_network = deployer.web3.eth.contract(
        abi=token_network_abi,
        address=token_network_address,
    )
    token_network = PrivateContract(token_network)

    log.info(
        f'Registered the token and created a TokenNetwork contract at {token_network_address}.',
    )

    txhash = token_contract.functions.approve(token_network.address, token_amount).transact(
        deployer.transaction,
        private_key=deployer.private_key,
    )
    log.debug(f'Aproving tokens for the TokenNetwork contract txHash={encode_hex(txhash)}')
    check_succesful_tx(deployer.web3, txhash, deployer.wait)

    assert token_contract.functions.allowance(
        deployer.owner,
        token_network.address,
    ).call() >= token_amount
    log.info(
        f'Approved {token_amount} tokens for the TokenNetwork contract '
        f'from owner {deployer.owner}.',
    )

    return (token_network_registry, token_network, token_contract)


def open_and_deposit(
        A,
        B,
        token_network,
        deployer,
        channel_identifier=None,
        txn_success_status=True,
):
    try:
        txhash = token_network.functions.openChannel(A, B, DEPLOY_SETTLE_TIMEOUT_MIN).transact(
            deployer.transaction,
            private_key=deployer.private_key,
        )
        log.debug(f'Opening a channel between {A} and {B} txHash={encode_hex(txhash)}')
        check_succesful_tx(deployer.web3, txhash, deployer.wait)

        # Get the channel identifier
        channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()
        success_status = True
    except ValueError as ex:
        success_status = False
        log.info(f'Cannot open a new channel {ex}')

    assert txn_success_status == success_status, \
        f'openChannel txn status is {success_status} instead of {txn_success_status}'

    assert channel_identifier is not None
    try:
        txhash = token_network.functions.setTotalDeposit(
            channel_identifier,
            A,
            int(MAX_ETH_CHANNEL_PARTICIPANT / 2),
            B,
        ).transact(
            deployer.transaction,
            private_key=deployer.private_key,
        )
        log.debug(
            f'Depositing {MAX_ETH_CHANNEL_PARTICIPANT} tokens for {A} in a channel with '
            f'identifier={channel_identifier} and partner= {B} txHash={encode_hex(txhash)}',
        )
        check_succesful_tx(deployer.web3, txhash, deployer.wait)
        success_status = True
    except ValueError as ex:
        success_status = False
        log.info(f'Cannot deposit more tokens in channel={channel_identifier}, {ex}')

    assert txn_success_status == success_status, \
        f'setTotalDeposit txn status is {success_status} instead of {txn_success_status}'

    try:
        txhash = token_network.functions.setTotalDeposit(
            channel_identifier,
            B,
            int(MAX_ETH_CHANNEL_PARTICIPANT / 2),
            A,
        ).transact(
            deployer.transaction,
            private_key=deployer.private_key,
        )
        log.debug(
            f'Depositing {MAX_ETH_CHANNEL_PARTICIPANT} tokens for {B} in a channel with '
            f'identifier={channel_identifier} and partner= {A} txHash={encode_hex(txhash)}',
        )
        check_succesful_tx(deployer.web3, txhash, deployer.wait)
        success_status = True
    except ValueError as ex:
        success_status = False
        log.info(f'Cannot deposit more tokens in channel={channel_identifier}, {ex}')

    assert txn_success_status == success_status, \
        f'setTotalDeposit txn status is {success_status} instead of {txn_success_status}'

    return channel_identifier


if __name__ == '__main__':
    deprecation_test()
