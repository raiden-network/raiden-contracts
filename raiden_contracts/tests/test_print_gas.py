from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    LIBRARY_TOKEN_NETWORK_UTILS,
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_SECRET_REGISTRY,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)
from raiden_contracts.utils.utils import get_pending_transfers_tree, get_locked_amount
from raiden_contracts.utils.merkle import get_merkle_root


def test_token_network_registry(
        web3,
        contracts_manager,
        contract_deployer_address,
        deploy_tester_contract,
        secret_registry_contract,
        custom_token,
        print_gas,
):
    # First deploy TokenNetworkUtils library and then link it
    (token_network_utils_library, txn_hash) = deploy_tester_contract(LIBRARY_TOKEN_NETWORK_UTILS)
    print_gas(txn_hash, LIBRARY_TOKEN_NETWORK_UTILS + ' DEPLOYMENT')

    libs = {
        '/Users/loredana/ETH/raiden-contracts': token_network_utils_library.address,
        '/home/travis/build/raiden-network/ra': token_network_utils_library.address,
    }
    (token_network_registry, txn_hash) = deploy_tester_contract(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        libs,
        [
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK_REGISTRY + ' DEPLOYMENT')

    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK_REGISTRY + '.createERC20TokenNetwork')


def test_token_network_create(
        print_gas,
        custom_token,
        secret_registry_contract,
        token_network_registry_contract,
):
    txn_hash = token_network_registry_contract.functions.createERC20TokenNetwork(
        custom_token.address,
    ).transact()

    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK_REGISTRY + ' createERC20TokenNetwork')


def test_secret_registry(secret_registry_contract, print_gas):
    secret = b'secretsecretsecretsecretsecretse'
    txn_hash = secret_registry_contract.functions.registerSecret(secret).transact()
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + '.registerSecret')


def test_channel_cycle(
        web3,
        print_gas,
        secret_registry_contract,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature,
):
    (A, B) = get_accounts(2)
    settle_timeout = 11

    (channel_identifier, txn_hash) = create_channel(A, B, settle_timeout)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + '.openChannel')

    txn_hash = channel_deposit(channel_identifier, A, 20, B)
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
