from typing import Callable, List, Optional

import pytest
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import (
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.contract_manager import gas_measurements
from raiden_contracts.tests.utils.constants import CONTRACT_DEPLOYER_ADDRESS
from raiden_contracts.utils.pending_transfers import get_locked_amount, get_pending_transfers_tree
from raiden_contracts.utils.proofs import sign_one_to_n_iou


@pytest.mark.parametrize("version", [None])
def test_gas_json_has_enough_fields(version: Optional[str]) -> None:
    """ Check is gas.json contains enough fields """
    doc = gas_measurements(version)
    keys = {
        "MonitoringService.claimReward",
        "MonitoringService.monitor",
        "OneToN.claim",
        "SecretRegistry.registerSecret",
        "TokenNetwork DEPLOYMENT",
        "TokenNetwork.closeChannel",
        "TokenNetwork.openChannel",
        "TokenNetwork.setTotalDeposit",
        "TokenNetwork.setTotalWithdraw",
        "TokenNetwork.settleChannel",
        "TokenNetwork.unlock 1 locks",
        "TokenNetwork.unlock 6 locks",
        "TokenNetwork.updateNonClosingBalanceProof",
        "TokenNetworkRegistry DEPLOYMENT",
        "TokenNetworkRegistry createERC20TokenNetwork",
        "UserDeposit.deposit",
        "UserDeposit.deposit (increase balance)",
        "UserDeposit.planWithdraw",
        "UserDeposit.withdraw",
    }
    assert set(doc.keys()) == keys


@pytest.fixture
def print_gas_token_network_registry(
    web3: Web3,
    deploy_tester_contract_txhash: Callable,
    secret_registry_contract: Contract,
    print_gas: Callable,
) -> None:
    """ Abusing pytest to print the deployment gas cost of TokenNetworkRegistry """
    txhash = deploy_tester_contract_txhash(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        [
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            10,
        ],
    )
    print_gas(txhash, CONTRACT_TOKEN_NETWORK_REGISTRY + " DEPLOYMENT")


@pytest.fixture
def print_gas_token_network_deployment(
    web3: Web3,
    get_accounts: Callable,
    print_gas: Callable,
    custom_token: Contract,
    secret_registry_contract: Contract,
    deploy_tester_contract_txhash: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """ Abusing pytest to print the deployment gas cost of TokenNetwork """
    deprecation_executor = get_accounts(1)[0]
    txhash = deploy_tester_contract_txhash(
        CONTRACT_TOKEN_NETWORK,
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
    print_gas(txhash, CONTRACT_TOKEN_NETWORK + " DEPLOYMENT")


@pytest.fixture
def print_gas_token_network_create(
    print_gas: Callable,
    custom_token: Contract,
    get_token_network_registry: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
    token_network_registry_constructor_args: List,
) -> None:
    """ Abusing pytest to print gas cost of TokenNetworkRegistry's createERC20TokenNetwork() """
    registry = get_token_network_registry(token_network_registry_constructor_args)
    txn_hash = registry.functions.createERC20TokenNetwork(
        custom_token.address, channel_participant_deposit_limit, token_network_deposit_limit
    ).call_and_transact({"from": CONTRACT_DEPLOYER_ADDRESS})

    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK_REGISTRY + " createERC20TokenNetwork")


@pytest.fixture
def print_gas_secret_registry(secret_registry_contract: Contract, print_gas: Callable) -> None:
    """ Abusing pytest to print gas cost of SecretRegistry's registerSecret() """
    secret = b"secretsecretsecretsecretsecretse"
    txn_hash = secret_registry_contract.functions.registerSecret(secret).call_and_transact()
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + ".registerSecret")


@pytest.fixture
def print_gas_channel_cycle(
    web3: Web3,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    withdraw_channel: Callable,
    secret_registry_contract: Contract,
    get_accounts: Callable,
    print_gas: Callable,
    create_balance_proof: Callable,
    create_balance_proof_update_signature: Callable,
) -> None:
    """ Abusing pytest to print gas costs of TokenNetwork's operations """
    (A, B, C, D) = get_accounts(4)
    settle_timeout = 11

    (channel_identifier, txn_hash) = create_channel(A, B, settle_timeout)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".openChannel")

    (_, txn_hash) = create_channel(C, D, settle_timeout)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".openChannel")

    txn_hash = channel_deposit(channel_identifier, A, 20, B)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".setTotalDeposit")

    txn_hash = channel_deposit(channel_identifier, B, 10, A)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".setTotalDeposit")

    txn_hash = withdraw_channel(channel_identifier, A, 5, B)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".setTotalWithdraw")

    pending_transfers_tree1 = get_pending_transfers_tree(web3, [1, 1, 2, 3], [2, 1])
    locksroot1 = pending_transfers_tree1.hash_of_packed_transfers
    locked_amount1 = get_locked_amount(pending_transfers_tree1.transfers)

    pending_transfers_tree2 = get_pending_transfers_tree(web3, [3], [], 7)
    locksroot2 = pending_transfers_tree2.hash_of_packed_transfers
    locked_amount2 = get_locked_amount(pending_transfers_tree2.transfers)

    balance_proof_A = create_balance_proof(
        channel_identifier, A, 10, locked_amount1, 5, locksroot1
    )
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, locked_amount2, 3, locksroot2)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B, channel_identifier, *balance_proof_A
    )

    for lock in pending_transfers_tree1.unlockable:
        txn_hash = secret_registry_contract.functions.registerSecret(lock[3]).call_and_transact(
            {"from": A}
        )
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + ".registerSecret")

    for lock in pending_transfers_tree2.unlockable:
        txn_hash = secret_registry_contract.functions.registerSecret(lock[3]).call_and_transact(
            {"from": A}
        )
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + ".registerSecret")

    txn_hash = token_network.functions.closeChannel(
        channel_identifier, B, *balance_proof_B
    ).call_and_transact({"from": A})
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".closeChannel")

    txn_hash = token_network.functions.updateNonClosingBalanceProof(
        channel_identifier, A, B, *balance_proof_A, balance_proof_update_signature_B
    ).call_and_transact({"from": B})
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".updateNonClosingBalanceProof")

    web3.testing.mine(settle_timeout)
    txn_hash = token_network.functions.settleChannel(
        channel_identifier, B, 5, locked_amount2, locksroot2, A, 10, locked_amount1, locksroot1
    ).call_and_transact()
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".settleChannel")

    txn_hash = token_network.functions.unlock(
        channel_identifier, A, B, pending_transfers_tree2.packed_transfers
    ).call_and_transact()
    print_gas(
        txn_hash,
        "{0}.unlock {1} locks".format(
            CONTRACT_TOKEN_NETWORK, len(pending_transfers_tree2.transfers)
        ),
    )

    txn_hash = token_network.functions.unlock(
        channel_identifier, B, A, pending_transfers_tree1.packed_transfers
    ).call_and_transact()
    print_gas(
        txn_hash,
        "{0}.unlock {1} locks".format(
            CONTRACT_TOKEN_NETWORK, len(pending_transfers_tree1.transfers)
        ),
    )


@pytest.fixture
def print_gas_monitoring_service(
    token_network: Contract,
    monitoring_service_external: Contract,
    get_accounts: Callable,
    create_channel: Callable,
    create_balance_proof: Callable,
    create_balance_proof_update_signature: Callable,
    create_reward_proof: Callable,
    service_registry: Contract,
    custom_token: Contract,
    deposit_to_udc: Callable,
    print_gas: Callable,
) -> None:
    """ Abusing pytest to print gas cost of MonitoringService functions """
    # setup: two parties + MS
    (A, B, MS) = get_accounts(3)
    reward_amount = 10
    deposit_to_udc(B, reward_amount)

    # register MS in the ServiceRegistry contract
    custom_token.functions.mint(50).call_and_transact({"from": MS})
    custom_token.functions.approve(service_registry.address, 20).call_and_transact({"from": MS})
    service_registry.functions.deposit(20).call_and_transact({"from": MS})

    # open a channel (c1, c2)
    channel_identifier = create_channel(A, B)[0]

    # create balance and reward proofs
    balance_proof_A = create_balance_proof(channel_identifier, B, transferred_amount=10, nonce=1)
    balance_proof_B = create_balance_proof(channel_identifier, A, transferred_amount=20, nonce=2)
    non_closing_signature_B = create_balance_proof_update_signature(
        B, channel_identifier, *balance_proof_B
    )
    reward_proof = create_reward_proof(
        signer=B,
        channel_identifier=channel_identifier,
        reward_amount=reward_amount,
        token_network_address=token_network.address,
        nonce=balance_proof_B[1],
        monitoring_service_contract_address=monitoring_service_external.address,
    )

    # c1 closes channel
    txn_hash = token_network.functions.closeChannel(
        channel_identifier, B, *balance_proof_A
    ).call_and_transact({"from": A})
    token_network.web3.testing.mine(4)

    # MS calls `MSC::monitor()` using c1's BP and reward proof
    txn_hash = monitoring_service_external.functions.monitor(
        A,
        B,
        balance_proof_B[0],  # balance_hash
        balance_proof_B[1],  # nonce
        balance_proof_B[2],  # additional_hash
        balance_proof_B[3],  # closing signature
        non_closing_signature_B,  # non-closing signature
        reward_proof[1],  # reward amount
        token_network.address,  # token network address
        reward_proof[5],  # reward proof signature
    ).call_and_transact({"from": MS})
    print_gas(txn_hash, CONTRACT_MONITORING_SERVICE + ".monitor")

    token_network.web3.testing.mine(1)

    # MS claims the reward
    txn_hash = monitoring_service_external.functions.claimReward(
        channel_identifier, token_network.address, A, B
    ).call_and_transact({"from": MS})
    print_gas(txn_hash, CONTRACT_MONITORING_SERVICE + ".claimReward")


@pytest.fixture
def print_gas_one_to_n(
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    get_private_key: Callable,
    web3: Web3,
    print_gas: Callable,
) -> None:
    """ Abusing pytest to print gas cost of OneToN functions """
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 30)

    # happy case
    chain_id = int(web3.version.network)
    amount = 10
    expiration = web3.eth.blockNumber + 2
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration_block=expiration,
        one_to_n_address=one_to_n_contract.address,
        chain_id=chain_id,
    )
    txn_hash = one_to_n_contract.functions.claim(
        A, B, amount, expiration, one_to_n_contract.address, signature
    ).call_and_transact({"from": A})
    print_gas(txn_hash, CONTRACT_ONE_TO_N + ".claim")


@pytest.fixture
def print_gas_user_deposit(
    user_deposit_contract: Contract,
    custom_token: Contract,
    get_accounts: Callable,
    web3: Web3,
    print_gas: Callable,
) -> None:
    """ Abusing pytest to print gas cost of UserDeposit functions

    The `transfer` function is not included because it's only called by trusted
    contracts as part of another function.
    """
    (A,) = get_accounts(1)
    custom_token.functions.mint(20).call_and_transact({"from": A})
    custom_token.functions.approve(user_deposit_contract.address, 20).call_and_transact(
        {"from": A}
    )

    # deposit
    txn_hash = user_deposit_contract.functions.deposit(A, 10).call_and_transact({"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".deposit")
    txn_hash = user_deposit_contract.functions.deposit(A, 20).call_and_transact({"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".deposit (increase balance)")

    # plan withdraw
    txn_hash = user_deposit_contract.functions.planWithdraw(10).call_and_transact({"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".planWithdraw")

    # withdraw
    withdraw_delay = user_deposit_contract.functions.withdraw_delay().call()
    web3.testing.mine(withdraw_delay)
    txn_hash = user_deposit_contract.functions.withdraw(10).call_and_transact({"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".withdraw")


# All gas printing is done in a single test. Otherwise, after a parallel
# execution of multiple gas printing tests, you see a corrupted gas.json.
@pytest.mark.slow
@pytest.mark.usefixtures(
    "print_gas_token_network_registry",
    "print_gas_token_network_deployment",
    "print_gas_token_network_create",
    "print_gas_secret_registry",
    "print_gas_channel_cycle",
    "print_gas_monitoring_service",
    "print_gas_one_to_n",
    "print_gas_user_deposit",
)
def test_print_gas() -> None:
    pass
