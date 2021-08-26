from typing import Callable, Dict, List, Optional

import pytest
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import (
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
    MessageTypeId,
)
from raiden_contracts.contract_manager import gas_measurements
from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.tests.utils.constants import DEPLOYER_ADDRESS, SERVICE_DEPOSIT, UINT256_MAX
from raiden_contracts.utils.pending_transfers import get_locked_amount, get_pending_transfers_tree
from raiden_contracts.utils.proofs import sign_one_to_n_iou, sign_reward_proof
from raiden_contracts.utils.type_aliases import BlockExpiration, ChainID, TokenAmount


@pytest.mark.parametrize("version", [None])
def test_gas_json_has_enough_fields(version: Optional[str]) -> None:
    """Check is gas.json contains enough fields"""
    doc = gas_measurements(version)
    keys = {
        "CustomToken.mint",
        "CustomToken.approve",
        "CustomToken.transfer",
        "CustomToken.transferFrom",
        "MonitoringService.claimReward",
        "MonitoringService.monitor",
        "OneToN.claim",
        "OneToN.bulkClaim 1 ious",
        "OneToN.bulkClaim 6 ious",
        "SecretRegistry.registerSecret",
        "SecretRegistry.registerSecretBatch1",
        "SecretRegistry.registerSecretBatch2",
        "SecretRegistry.registerSecretBatch3",
        "ServiceRegistry.deposit",
        "ServiceRegistry.setURL",
        "TokenNetwork DEPLOYMENT",
        "TokenNetwork.closeChannel",
        "TokenNetwork.cooperativeSettle",
        "TokenNetwork.openChannel",
        "TokenNetwork.openChannelWithDeposit",
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
    deploy_tester_contract_txhash: Callable,
    secret_registry_contract: Contract,
    print_gas: Callable,
) -> None:
    """Abusing pytest to print the deployment gas cost of TokenNetworkRegistry"""
    txhash = deploy_tester_contract_txhash(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        _secret_registry_address=secret_registry_contract.address,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
        _max_token_networks=10,
    )
    print_gas(txhash, CONTRACT_TOKEN_NETWORK_REGISTRY + " DEPLOYMENT")


@pytest.fixture
def print_gas_token_network_deployment(
    get_accounts: Callable,
    print_gas: Callable,
    custom_token: Contract,
    secret_registry_contract: Contract,
    deploy_tester_contract_txhash: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """Abusing pytest to print the deployment gas cost of TokenNetwork"""
    controller = get_accounts(1)[0]
    txhash = deploy_tester_contract_txhash(
        CONTRACT_TOKEN_NETWORK,
        _token_address=custom_token.address,
        _secret_registry=secret_registry_contract.address,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
        _controller=controller,
        _channel_participant_deposit_limit=channel_participant_deposit_limit,
        _token_network_deposit_limit=token_network_deposit_limit,
    )
    print_gas(txhash, CONTRACT_TOKEN_NETWORK + " DEPLOYMENT")


@pytest.fixture
def print_gas_token_network_create(
    print_gas: Callable,
    custom_token: Contract,
    get_token_network_registry: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
    token_network_registry_constructor_args: Dict,
) -> None:
    """Abusing pytest to print gas cost of TokenNetworkRegistry's createERC20TokenNetwork()"""
    registry = get_token_network_registry(**token_network_registry_constructor_args)
    txn_hash = call_and_transact(
        registry.functions.createERC20TokenNetwork(
            custom_token.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ),
        {"from": DEPLOYER_ADDRESS},
    )

    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK_REGISTRY + " createERC20TokenNetwork")


@pytest.fixture
def print_gas_secret_registry(secret_registry_contract: Contract, print_gas: Callable) -> None:
    """Abusing pytest to print gas cost of SecretRegistry's registerSecret()"""
    secret = b"secretsecretsecretsecretsecretse"
    txn_hash = call_and_transact(secret_registry_contract.functions.registerSecret(secret))
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + ".registerSecret")

    for batch_size in (1, 2, 3):
        batch = [bytes([batch_size, i] + [0] * 30) for i in range(batch_size)]
        txn_hash = call_and_transact(secret_registry_contract.functions.registerSecretBatch(batch))
        print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + ".registerSecretBatch" + str(batch_size))


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
    create_balance_proof_countersignature: Callable,
) -> None:
    """Abusing pytest to print gas costs of TokenNetwork's operations"""
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

    txn_hash = withdraw_channel(channel_identifier, A, 5, UINT256_MAX, B)
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
    balance_proof_update_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_A._asdict(),
    )
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, locked_amount2, 3, locksroot2)
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )

    for lock in pending_transfers_tree1.unlockable:
        txn_hash = call_and_transact(
            secret_registry_contract.functions.registerSecret(lock[3]), {"from": A}
        )
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + ".registerSecret")

    for lock in pending_transfers_tree2.unlockable:
        txn_hash = call_and_transact(
            secret_registry_contract.functions.registerSecret(lock[3]), {"from": A}
        )
    print_gas(txn_hash, CONTRACT_SECRET_REGISTRY + ".registerSecret")

    txn_hash = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".closeChannel")

    txn_hash = call_and_transact(
        token_network.functions.updateNonClosingBalanceProof(
            channel_identifier,
            A,
            B,
            *balance_proof_A._asdict().values(),
            balance_proof_update_signature_B,
        ),
        {"from": B},
    )
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".updateNonClosingBalanceProof")

    mine_blocks(web3, settle_timeout)
    txn_hash = call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier,
            B,
            5,
            locked_amount2,
            locksroot2,
            A,
            10,
            locked_amount1,
            locksroot1,
        )
    )
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".settleChannel")

    txn_hash = call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree2.packed_transfers
        )
    )
    print_gas(
        txn_hash,
        "{0}.unlock {1} locks".format(
            CONTRACT_TOKEN_NETWORK, len(pending_transfers_tree2.transfers)
        ),
    )

    txn_hash = call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree1.packed_transfers
        )
    )
    print_gas(
        txn_hash,
        "{0}.unlock {1} locks".format(
            CONTRACT_TOKEN_NETWORK, len(pending_transfers_tree1.transfers)
        ),
    )


@pytest.fixture
def print_gas_channel_open_with_deposit(
    token_network: Contract,
    get_accounts: Callable,
    print_gas: Callable,
    assign_tokens: Callable,
) -> None:
    """Abusing pytest to print gas costs of TokenNetwork's `openChannelWithDeposit`"""
    (A, B) = get_accounts(2)
    settle_timeout = 11
    deposit = 20

    assign_tokens(A, deposit)
    tx_hash = call_and_transact(
        token_network.functions.openChannelWithDeposit(A, B, settle_timeout, deposit),
        {"from": A},
    )
    print_gas(tx_hash, CONTRACT_TOKEN_NETWORK + ".openChannelWithDeposit")


@pytest.fixture
def print_gas_coop_settle(
    create_channel: Callable,
    channel_deposit: Callable,
    cooperative_settle_channel: Callable,
    get_accounts: Callable,
    print_gas: Callable,
) -> None:
    """Abusing pytest to print gas costs of cooperative settle"""
    (A, B) = get_accounts(2)
    settle_timeout = 11

    (channel_identifier, txn_hash) = create_channel(A, B, settle_timeout)
    channel_deposit(channel_identifier, A, 20, B)

    txn_hash = cooperative_settle_channel(channel_identifier, A, B, 10, 10, UINT256_MAX, A)
    print_gas(txn_hash, CONTRACT_TOKEN_NETWORK + ".cooperativeSettle")


@pytest.fixture
def print_gas_monitoring_service(
    token_network: Contract,
    monitoring_service_external: Contract,
    get_accounts: Callable,
    create_channel: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    service_registry: Contract,
    custom_token: Contract,
    deposit_to_udc: Callable,
    print_gas: Callable,
    get_private_key: Callable,
    create_service_account: Callable,
    web3: Web3,
) -> None:
    """Abusing pytest to print gas cost of MonitoringService functions"""
    # setup: two parties + MS
    (A, MS) = get_accounts(2)
    B = create_service_account()
    reward_amount = TokenAmount(10)
    deposit_to_udc(B, reward_amount)

    # register MS in the ServiceRegistry contract
    call_and_transact(custom_token.functions.mint(SERVICE_DEPOSIT * 2), {"from": MS})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, SERVICE_DEPOSIT),
        {"from": MS},
    )
    call_and_transact(service_registry.functions.deposit(SERVICE_DEPOSIT), {"from": MS})

    # open a channel (c1, c2)
    channel_identifier = create_channel(A, B)[0]

    # create balance and reward proofs
    balance_proof_A = create_balance_proof(channel_identifier, B, transferred_amount=10, nonce=1)
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_A._asdict(),
    )
    balance_proof_B = create_balance_proof(channel_identifier, A, transferred_amount=20, nonce=2)
    non_closing_signature_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF_UPDATE,
        **balance_proof_B._asdict(),
    )
    reward_proof_signature = sign_reward_proof(
        privatekey=get_private_key(B),
        monitoring_service_contract_address=monitoring_service_external.address,
        chain_id=token_network.functions.chain_id().call(),
        token_network_address=token_network.address,
        non_closing_participant=B,
        reward_amount=reward_amount,
        non_closing_signature=non_closing_signature_B,
    )

    # c1 closes channel
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_A._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )
    mine_blocks(web3, 4)

    # MS calls `MSC::monitor()` using c1's BP and reward proof
    txn_hash = call_and_transact(
        monitoring_service_external.functions.monitor(
            A,
            B,
            balance_proof_B.balance_hash,
            balance_proof_B.nonce,
            balance_proof_B.additional_hash,
            balance_proof_B.original_signature,
            non_closing_signature_B,  # non-closing signature
            reward_amount,
            token_network.address,  # token network address
            reward_proof_signature,
        ),
        {"from": MS},
    )
    print_gas(txn_hash, CONTRACT_MONITORING_SERVICE + ".monitor")

    mine_blocks(web3, 1)

    # MS claims the reward
    txn_hash = call_and_transact(
        monitoring_service_external.functions.claimReward(
            channel_identifier, token_network.address, A, B
        ),
        {"from": MS},
    )
    print_gas(txn_hash, CONTRACT_MONITORING_SERVICE + ".claimReward")


@pytest.fixture
def print_gas_one_to_n(
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    print_gas: Callable,
    make_iou: Callable,
    web3: Web3,
    get_private_key: Callable,
    create_service_account: Callable,
    create_account: Callable,
) -> None:
    """Abusing pytest to print gas cost of OneToN functions"""
    A = create_account()
    B = create_service_account()
    deposit_to_udc(A, 30)

    # happy case
    chain_id = web3.eth.chain_id
    amount = TokenAmount(10)
    expiration = BlockExpiration(web3.eth.block_number + 2)
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration_block=expiration,
        one_to_n_address=one_to_n_contract.address,
        chain_id=ChainID(chain_id),
    )
    txn_hash = call_and_transact(
        one_to_n_contract.functions.claim(A, B, amount, expiration, signature),
        {"from": A},
    )

    print_gas(txn_hash, CONTRACT_ONE_TO_N + ".claim")

    # bulk claims gas prices
    def concat_iou_data(ious: List[Dict], key: str) -> List:
        return [iou[key] for iou in ious]

    def concat_iou_signatures(ious: List[Dict]) -> bytes:
        result = b""
        for iou in ious:
            result += iou["signature"]

        return result

    for num_ious in (1, 6):
        receivers = [create_service_account() for i in range(num_ious)]
        ious = [make_iou(A, r) for r in receivers]

        txn_hash = call_and_transact(
            one_to_n_contract.functions.bulkClaim(
                concat_iou_data(ious, "sender"),
                concat_iou_data(ious, "receiver"),
                concat_iou_data(ious, "amount"),
                concat_iou_data(ious, "expiration_block"),
                concat_iou_signatures(ious),
            ),
            {"from": A},
        )
        print_gas(txn_hash, CONTRACT_ONE_TO_N + f".bulkClaim {num_ious} ious")


@pytest.fixture
def print_gas_user_deposit(
    user_deposit_contract: Contract,
    custom_token: Contract,
    get_accounts: Callable,
    web3: Web3,
    print_gas: Callable,
) -> None:
    """Abusing pytest to print gas cost of UserDeposit functions

    The `transfer` function is not included because it's only called by trusted
    contracts as part of another function.
    """
    (A,) = get_accounts(1)
    call_and_transact(custom_token.functions.mint(20), {"from": A})
    call_and_transact(
        custom_token.functions.approve(user_deposit_contract.address, 20), {"from": A}
    )

    # deposit
    txn_hash = call_and_transact(user_deposit_contract.functions.deposit(A, 10), {"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".deposit")
    txn_hash = call_and_transact(user_deposit_contract.functions.deposit(A, 20), {"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".deposit (increase balance)")

    # plan withdraw
    txn_hash = call_and_transact(user_deposit_contract.functions.planWithdraw(10), {"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".planWithdraw")

    # withdraw
    withdraw_delay = user_deposit_contract.functions.withdraw_delay().call()
    mine_blocks(web3, withdraw_delay)
    txn_hash = call_and_transact(user_deposit_contract.functions.withdraw(10), {"from": A})
    print_gas(txn_hash, CONTRACT_USER_DEPOSIT + ".withdraw")


@pytest.fixture
def print_gas_service_registry(
    custom_token: Contract,
    service_registry: Contract,
    print_gas: Callable,
    create_account: Callable,
) -> None:
    A = create_account()
    deposit = service_registry.functions.currentPrice().call()
    call_and_transact(custom_token.functions.mint(deposit), {"from": A})
    call_and_transact(
        custom_token.functions.approve(service_registry.address, deposit), {"from": A}
    )
    deposit_tx = call_and_transact(service_registry.functions.deposit(deposit), {"from": A})
    print_gas(deposit_tx, CONTRACT_SERVICE_REGISTRY + ".deposit")
    url = "http://example.com"
    set_url_tx = call_and_transact(service_registry.functions.setURL(url), {"from": A})
    print_gas(set_url_tx, CONTRACT_SERVICE_REGISTRY + ".setURL")


@pytest.fixture
def print_gas_token(get_accounts: Callable, custom_token: Contract, print_gas: Callable) -> None:
    (A, B) = get_accounts(2)
    tx_hash = call_and_transact(custom_token.functions.mint(100), {"from": A})
    print_gas(tx_hash, "CustomToken.mint")
    tx_hash = call_and_transact(custom_token.functions.transfer(B, 100), {"from": A})
    print_gas(tx_hash, "CustomToken.transfer")
    tx_hash = call_and_transact(custom_token.functions.approve(A, 100), {"from": B})
    print_gas(tx_hash, "CustomToken.approve")
    tx_hash = call_and_transact(custom_token.functions.transferFrom(B, A, 100), {"from": A})
    print_gas(tx_hash, "CustomToken.transferFrom")


# All gas printing is done in a single test. Otherwise, after a parallel
# execution of multiple gas printing tests, you see a corrupted gas.json.
@pytest.mark.slow
@pytest.mark.usefixtures(
    "print_gas_token_network_registry",
    "print_gas_token_network_deployment",
    "print_gas_token_network_create",
    "print_gas_secret_registry",
    "print_gas_channel_cycle",
    "print_gas_channel_open_with_deposit",
    "print_gas_coop_settle",
    "print_gas_monitoring_service",
    "print_gas_one_to_n",
    "print_gas_service_registry",
    "print_gas_user_deposit",
    "print_gas_token",
)
def test_print_gas() -> None:
    pass
