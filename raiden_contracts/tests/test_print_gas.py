import json

import pytest

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.contract_manager import contracts_gas_path
from raiden_contracts.tests.utils.constants import CONTRACT_DEPLOYER_ADDRESS, EMPTY_LOCKSROOT
from raiden_contracts.utils.merkle import get_merkle_root
from raiden_contracts.utils.pending_transfers import get_locked_amount, get_pending_transfers_tree
from raiden_contracts.utils.proofs import sign_one_to_n_iou


@pytest.mark.parametrize('version', [None, '0.9.0'])
def test_gas_json_has_enough_fields(version):
    """ Check is gas.json contains enough fields """
    with contracts_gas_path(version).open(mode='r') as gas_file:
        doc = json.load(gas_file)
        keys = {
            'EndpointRegistry.registerEndpoint',
            'MonitoringService.claimReward',
            'MonitoringService.monitor',
            'OneToN.claim',
            'SecretRegistry.registerSecret',
            'TokenNetwork DEPLOYMENT',
            'TokenNetwork.closeChannel',
            'TokenNetwork.openChannel',
            'TokenNetwork.setTotalDeposit',
            'TokenNetwork.settleChannel',
            'TokenNetwork.unlock 1 locks',
            'TokenNetwork.unlock 6 locks',
            'TokenNetwork.updateNonClosingBalanceProof',
            'TokenNetworkRegistry DEPLOYMENT',
            'TokenNetworkRegistry createERC20TokenNetwork',
            'UserDeposit.deposit',
            'UserDeposit.deposit (increase balance)',
            'UserDeposit.planWithdraw',
            'UserDeposit.withdraw',
        }
        assert set(doc.keys()) == keys


@pytest.fixture
def print_gas_token_network_registry(
        web3,
        deploy_tester_contract_txhash,
        secret_registry_contract,
        custom_token,
        print_gas,
):
    """ Abusing pytest to print the deployment gas cost of TokenNetworkRegistry """
    txhash = deploy_tester_contract_txhash(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        [],
        [
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            10,
        ],
    )
    print_gas(txhash, CONTRACT_TOKEN_NETWORK_REGISTRY + ' DEPLOYMENT')


@pytest.fixture
def print_gas_token_network_deployment(
        web3,
        get_accounts,
        print_gas,
        custom_token,
        secret_registry_contract,
        deploy_tester_contract_txhash,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    """ Abusing pytest to print the deployment gas cost of TokenNetwork """
    deprecation_executor = get_accounts(1)[0]
    txhash = deploy_tester_contract_txhash(
        CONTRACT_TOKEN_NETWORK,
        [],
        [
            custom_token.address,
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            deprecation_executor,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ],
    )
    print_gas(txhash, CONTRACT_TOKEN_NETWORK + ' DEPLOYMENT')


@pytest.fixture
def print_gas_token_network_create(
        print_gas,
        custom_token,
        secret_registry_contract,
        get_token_network_registry,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
        token_network_registry_constructor_args,
):
    """ Abusing pytest to print gas cost of TokenNetworkRegistry's createERC20TokenNetwork() """
    registry = get_token_network_registry(token_network_registry_constructor_args)
    txn_hash = registry.functions.createERC20TokenNetwork(
        custom_token.address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
    ).call_and_transact({'from': CONTRACT_DEPLOYER_ADDRESS})

    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK_REGISTRY + ' createERC20TokenNetwork')


@pytest.fixture
def print_gas_secret_registry(secret_registry_contract, print_gas):
    """ Abusing pytest to print gas cost of SecretRegistry's registerSecret() """
    secret = b'secretsecretsecretsecretsecretse'
    txn_hash = secret_registry_contract.functions.registerSecret(secret).call_and_transact()
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + '.registerSecret')


@pytest.fixture
def print_gas_channel_cycle(
        web3,
        token_network,
        create_channel,
        channel_deposit,
        secret_registry_contract,
        get_accounts,
        print_gas,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    """ Abusing pytest to print gas costs of TokenNetwork's operations """
    (A, B, C, D) = get_accounts(4)
    settle_timeout = 11

    (channel_identifier, txn_hash) = create_channel(A, B, settle_timeout)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.openChannel')

    (_, txn_hash) = create_channel(C, D, settle_timeout)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.openChannel')

    txn_hash = channel_deposit(channel_identifier, A, 20, B)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.setTotalDeposit')

    txn_hash = channel_deposit(channel_identifier, B, 10, A)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.setTotalDeposit')

    pending_transfers_tree1 = get_pending_transfers_tree(web3, [1, 1, 2, 3], [2, 1])
    locksroot1 = get_merkle_root(pending_transfers_tree1.merkle_tree)
    locked_amount1 = get_locked_amount(pending_transfers_tree1.transfers)

    pending_transfers_tree2 = get_pending_transfers_tree(web3, [3], [], 7)
    locksroot2 = get_merkle_root(pending_transfers_tree2.merkle_tree)
    locked_amount2 = get_locked_amount(pending_transfers_tree2.transfers)

    balance_proof_A = create_balance_proof(
        channel_identifier,
        A,
        10,
        locked_amount1,
        5,
        locksroot1,
    )
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        5,
        locked_amount2,
        3,
        locksroot2,
    )
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A,
    )

    for lock in pending_transfers_tree1.unlockable:
        txn_hash = secret_registry_contract.functions.registerSecret(
            lock[3],
        ).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + '.registerSecret')

    for lock in pending_transfers_tree2.unlockable:
        txn_hash = secret_registry_contract.functions.registerSecret(
            lock[3],
        ).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + '.registerSecret')

    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.closeChannel')

    txn_hash = token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).call_and_transact({'from': B})
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.updateNonClosingBalanceProof')

    web3.testing.mine(settle_timeout)
    txn_hash = token_network.functions.settleChannel(
        channel_identifier,
        B,
        5,
        locked_amount2,
        locksroot2,
        A,
        10,
        locked_amount1,
        locksroot1,
    ).call_and_transact()
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.settleChannel')

    txn_hash = token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree2.packed_transfers,
    ).call_and_transact()
    print_gas(txn_hash, '{0}.unlock {1} locks'.format(
        CONTRACT_TOKEN_NETWORK,
        len(pending_transfers_tree2.transfers),
    ))

    txn_hash = token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree1.packed_transfers,
    ).call_and_transact()
    print_gas(txn_hash, '{0}.unlock {1} locks'.format(
        CONTRACT_TOKEN_NETWORK,
        len(pending_transfers_tree1.transfers),
    ))


@pytest.fixture
def print_gas_endpointregistry(endpoint_registry_contract, get_accounts, print_gas):
    """ Abusing pytest to print gas cost of EndpointRegistry's registerEndpoint() """
    A = get_accounts(1)[0]
    ENDPOINT = '127.0.0.1:38647'
    txn_hash = endpoint_registry_contract.functions.registerEndpoint(ENDPOINT).call_and_transact({
        'from': A,
    })
    print_gas(txn_hash, CONTRACT_ENDPOINT_REGISTRY + '.registerEndpoint')


@pytest.fixture
def print_gas_monitoring_service(
        token_network,
        monitoring_service_external,
        get_accounts,
        create_channel,
        create_balance_proof,
        create_balance_proof_update_signature,
        create_reward_proof,
        service_registry,
        custom_token,
        deposit_to_udc,
        print_gas,
):
    """ Abusing pytest to print gas cost of MonitoringService functions """
    # setup: two parties + MS
    (A, B, MS) = get_accounts(3)
    reward_amount = 10
    deposit_to_udc(B, reward_amount)

    # register MS in the ServiceRegistry contract
    custom_token.functions.mint(50).call_and_transact({'from': MS})
    custom_token.functions.approve(service_registry.address, 20).call_and_transact({'from': MS})
    service_registry.functions.deposit(20).call_and_transact({'from': MS})

    # open a channel (c1, c2)
    channel_identifier = create_channel(A, B)[0]

    # create balance and reward proofs
    balance_proof_A = create_balance_proof(channel_identifier, B, transferred_amount=10, nonce=1)
    balance_proof_B = create_balance_proof(channel_identifier, A, transferred_amount=20, nonce=2)
    non_closing_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_B,
    )
    reward_proof = create_reward_proof(
        B,
        channel_identifier,
        reward_amount,
        token_network.address,
        nonce=balance_proof_B[1],
    )

    # c1 closes channel
    txn_hash = token_network.functions.closeChannel(
        channel_identifier, B, *balance_proof_A,
    ).call_and_transact({'from': A})

    # MS calls `MSC::monitor()` using c1's BP and reward proof
    txn_hash = monitoring_service_external.functions.monitor(
        A,
        B,
        balance_proof_B[0],       # balance_hash
        balance_proof_B[1],       # nonce
        balance_proof_B[2],       # additional_hash
        balance_proof_B[3],       # closing signature
        non_closing_signature_B,  # non-closing signature
        reward_proof[1],          # reward amount
        token_network.address,    # token network address
        reward_proof[5],          # reward proof signature
    ).call_and_transact({'from': MS})
    print_gas(txn_hash, CONTRACT_MONITORING_SERVICE + '.monitor')

    # settle channel
    token_network.web3.testing.mine(8)
    token_network.functions.settleChannel(
        channel_identifier,
        B,                   # participant2
        10,                  # participant2_transferred_amount
        0,                   # participant2_locked_amount
        EMPTY_LOCKSROOT,     # participant2_locksroot
        A,                   # participant1
        20,                  # participant1_transferred_amount
        0,                   # participant1_locked_amount
        EMPTY_LOCKSROOT,     # participant1_locksroot
    ).call_and_transact()

    # MS claims the reward
    txn_hash = monitoring_service_external.functions.claimReward(
        channel_identifier,
        token_network.address,
        A,
        B,
    ).call_and_transact({'from': MS})
    print_gas(txn_hash, CONTRACT_MONITORING_SERVICE + '.claimReward')


@pytest.fixture
def print_gas_one_to_n(
        one_to_n_contract,
        deposit_to_udc,
        get_accounts,
        get_private_key,
        web3,
        print_gas,
):
    """ Abusing pytest to print gas cost of OneToN functions """
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 30)

    # happy case
    amount = 10
    expiration = web3.eth.blockNumber + 2
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration=expiration,
    )
    txn_hash = one_to_n_contract.functions.claim(
        A, B, amount, expiration, signature,
    ).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_ONE_TO_N + '.claim')


@pytest.fixture
def print_gas_user_deposit(
        user_deposit_contract,
        custom_token,
        get_accounts,
        web3,
        print_gas,
):
    """ Abusing pytest to print gas cost of UserDeposit functions

    The `transfer` function is not included because it's only called by trusted
    contracts as part of another function.
    """
    (A, ) = get_accounts(1)
    custom_token.functions.mint(20).call_and_transact({'from': A})
    custom_token.functions.approve(
        user_deposit_contract.address,
        20,
    ).call_and_transact({'from': A})

    # deposit
    txn_hash = user_deposit_contract.functions.deposit(A, 10).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + '.deposit')
    txn_hash = user_deposit_contract.functions.deposit(A, 20).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + '.deposit (increase balance)')

    # plan withdraw
    txn_hash = user_deposit_contract.functions.planWithdraw(10).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + '.planWithdraw')

    # withdraw
    withdraw_delay = user_deposit_contract.functions.withdraw_delay().call()
    web3.testing.mine(withdraw_delay)
    txn_hash = user_deposit_contract.functions.withdraw(10).call_and_transact({'from': A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + '.withdraw')


# All gas printing is done in a single test. Otherwise, after a parallel
# execution of multiple gas printing tests, you see a corrupted gas.json.
@pytest.mark.slow
def test_print_gas(
        print_gas_token_network_registry,
        print_gas_token_network_deployment,
        print_gas_token_network_create,
        print_gas_secret_registry,
        print_gas_channel_cycle,
        print_gas_endpointregistry,
        print_gas_monitoring_service,
        print_gas_one_to_n,
        print_gas_user_deposit,
):
    pass
