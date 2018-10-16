from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_SECRET_REGISTRY,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)
from raiden_contracts.utils.utils import get_pending_transfers_tree, get_locked_amount
from raiden_contracts.utils.merkle import get_merkle_root


def test_token_network_registry(
        web3,
        deploy_tester_contract_txhash,
        secret_registry_contract,
        custom_token,
        print_gas,
):
    txhash = deploy_tester_contract_txhash(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        [],
        [
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )
    print_gas(txhash, CONTRACT_TOKEN_NETWORK_REGISTRY + ' DEPLOYMENT')


def test_token_network_deployment(
        web3,
        get_accounts,
        print_gas,
        custom_token,
        secret_registry_contract,
        deploy_tester_contract_txhash,
):
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
        ],
    )
    print_gas(txhash, CONTRACT_TOKEN_NETWORK + ' DEPLOYMENT')


def test_token_network_create(
        print_gas,
        custom_token,
        secret_registry_contract,
        token_network_registry_contract,
        contract_deployer_address,
):
    txn_hash = token_network_registry_contract.functions.createERC20TokenNetwork(
        custom_token.address,
    ).transact({'from': contract_deployer_address})

    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK_REGISTRY + ' createERC20TokenNetwork')


def test_secret_registry(secret_registry_contract, print_gas):
    secret = b'secretsecretsecretsecretsecretse'
    txn_hash = secret_registry_contract.functions.registerSecret(secret).transact()
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + '.registerSecret')


def test_channel_cycle(
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
    (A, B, C, D) = get_accounts(4)
    settle_timeout = 11

    (channel_identifier, txn_hash) = create_channel(A, B, settle_timeout)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.openChannel')

    (channel_identifier2, txn_hash) = create_channel(C, D, settle_timeout)
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
        txn_hash = secret_registry_contract.functions.registerSecret(lock[3]).transact({'from': A})
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + '.registerSecret')

    for lock in pending_transfers_tree2.unlockable:
        txn_hash = secret_registry_contract.functions.registerSecret(lock[3]).transact({'from': A})
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + '.registerSecret')

    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof_B,
    ).transact({'from': A})
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.closeChannel')

    txn_hash = token_network.functions.updateNonClosingBalanceProof(
        channel_identifier,
        A,
        B,
        *balance_proof_A,
        balance_proof_update_signature_B,
    ).transact({'from': B})
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
    ).transact()
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.settleChannel')

    txn_hash = token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree2.packed_transfers,
    ).transact()
    print_gas(txn_hash, '{0}.unlock {1} locks'.format(
        CONTRACT_TOKEN_NETWORK,
        len(pending_transfers_tree2.transfers),
    ))

    txn_hash = token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree1.packed_transfers,
    ).transact()
    print_gas(txn_hash, '{0}.unlock {1} locks'.format(
        CONTRACT_TOKEN_NETWORK,
        len(pending_transfers_tree1.transfers),
    ))


def test_endpointregistry_gas(endpoint_registry_contract, get_accounts, print_gas):
    (A, B) = get_accounts(2)
    ENDPOINT = '127.0.0.1:38647'
    txn_hash = endpoint_registry_contract.functions.registerEndpoint(ENDPOINT).transact({
        'from': A,
    })
    print_gas(txn_hash, CONTRACT_ENDPOINT_REGISTRY + '.registerEndpoint')
