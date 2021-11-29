from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract, get_event_data

from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    EVENT_DEPRECATION_SWITCH,
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.utils import ChannelValues, LockedAmounts, call_and_transact
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.pending_transfers import (
    get_pending_transfers_tree_with_generated_lists,
)


def test_controller(
    web3: Web3,
    contracts_manager: ContractManager,
    deploy_tester_contract: Callable,
    secret_registry_contract: Contract,
    custom_token: Contract,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
    get_accounts: Callable,
) -> None:
    """A creates a TokenNetworkRegistry and B registers a TokenNetwork

    This test is mainly a happy-path scenario. One Ethereum account creates a
    TokenNetworkRegistry, registers a TokenNetwork. TokenNetworkRegistry emits
    events that shows the new TokenNetwork. The new TokenNetwork has the
    original account as the deprecation executor. During these, this test also
    tries to register more than one TokenNetworks and see a failure.
    """
    (controller, B) = get_accounts(2)

    token_network_registry = deploy_tester_contract(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        controller,
        _secret_registry_address=secret_registry_contract.address,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
        _max_token_networks=1,
    )

    # Make sure deployer is controller
    assert token_network_registry.functions.controller().call() == controller
    assert token_network_registry.functions.token_network_created().call() == 0

    # We can only deploy one TokenNetwork contract
    # It can be deployed by anyone
    tx_hash = call_and_transact(
        token_network_registry.functions.createERC20TokenNetwork(
            custom_token.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ),
        {"from": B},
    )
    assert token_network_registry.functions.token_network_created().call() == 1

    # No other TokenNetworks can be deployed now
    with pytest.raises(TransactionFailed, match="TNR: registry full"):
        token_network_registry.functions.createERC20TokenNetwork(
            custom_token.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call({"from": B})
    with pytest.raises(TransactionFailed, match="TNR: registry full"):
        token_network_registry.functions.createERC20TokenNetwork(
            custom_token.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call({"from": controller})

    tx_receipt = web3.eth.get_transaction_receipt(tx_hash)
    event_abi = contracts_manager.get_event_abi(
        CONTRACT_TOKEN_NETWORK_REGISTRY, EVENT_TOKEN_NETWORK_CREATED
    )
    event_data = get_event_data(web3.codec, event_abi, tx_receipt["logs"][0])
    token_network_address = event_data["args"]["token_network_address"]
    token_network = web3.eth.contract(
        abi=contracts_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK),
        address=token_network_address,
    )

    assert token_network.functions.controller().call() == controller


def test_set_deprecation_switch(
    get_accounts: Callable,
    token_network: Contract,
    web3: Web3,
    contracts_manager: ContractManager,
) -> None:
    """The deprecation executor deprecates a TokenNetwork contract"""
    (A) = get_accounts(1)[0]
    controller = token_network.functions.controller().call()

    assert token_network.functions.safety_deprecation_switch().call() is False

    with pytest.raises(TransactionFailed, match="Can only be called by controller"):
        token_network.functions.deprecate().call({"from": A})

    tx = call_and_transact(token_network.functions.deprecate(), {"from": controller})
    assert token_network.functions.safety_deprecation_switch().call() is True
    tx_receipt = web3.eth.get_transaction_receipt(tx)
    event_abi = contracts_manager.get_event_abi(CONTRACT_TOKEN_NETWORK, EVENT_DEPRECATION_SWITCH)
    event_data = get_event_data(web3.codec, event_abi, tx_receipt["logs"][0])
    assert event_data["args"]["new_value"]

    # We should not be able to call it again
    with pytest.raises(TransactionFailed, match="TN: network is deprecated"):
        token_network.functions.deprecate().call({"from": A})


def test_deprecation_switch(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
) -> None:
    """Test the effects of the deprecation switch on deposits and channel opening"""

    controller = token_network.functions.controller().call()
    (A, B, C, D) = get_accounts(4)
    deposit = 100
    bigger_deposit = 200

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit, B)
    channel_deposit(channel_identifier, B, deposit, A)

    call_and_transact(token_network.functions.deprecate(), {"from": controller})
    assert token_network.functions.safety_deprecation_switch().call() is True

    # Now we cannot deposit in existent channels
    with pytest.raises(TransactionFailed, match="TN: network is deprecated"):
        channel_deposit(channel_identifier, A, bigger_deposit, B)
    with pytest.raises(TransactionFailed, match="TN: network is deprecated"):
        channel_deposit(channel_identifier, B, bigger_deposit, A)

    # Now we cannot open channels anymore
    with pytest.raises(TransactionFailed, match="TN: network is deprecated"):
        channel_identifier = create_channel(C, D)[0]


def test_deprecation_switch_settle(
    web3: Web3,
    get_accounts: Callable,
    token_network: Contract,
    custom_token: Contract,
    reveal_secrets: Callable,
    create_channel: Callable,
    channel_deposit: Callable,
    close_and_update_channel: Callable,
) -> None:
    """Channel close and settlement still work after the depracation switch is turned on"""
    controller = token_network.functions.controller().call()
    (A, B) = get_accounts(2)
    deposit = 100

    (vals_A, vals_B) = (
        ChannelValues(
            deposit=deposit,
            withdrawn=0,
            transferred=5,
            locked_amounts=LockedAmounts(claimable_locked=2, unclaimable_locked=4),
        ),
        ChannelValues(
            deposit=deposit,
            withdrawn=0,
            transferred=10,
            locked_amounts=LockedAmounts(claimable_locked=4, unclaimable_locked=6),
        ),
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, vals_A.deposit, B)
    channel_deposit(channel_identifier, B, vals_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree_with_generated_lists(
        web3,
        unlockable_amount=vals_A.locked_amounts.claimable_locked,
        expired_amount=vals_A.locked_amounts.unclaimable_locked,
    )
    vals_A.locksroot = pending_transfers_tree_A.hash_of_packed_transfers
    # Reveal A's secrets.
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree_with_generated_lists(
        web3,
        unlockable_amount=vals_B.locked_amounts.claimable_locked,
        expired_amount=vals_B.locked_amounts.unclaimable_locked,
    )
    vals_B.locksroot = pending_transfers_tree_B.hash_of_packed_transfers
    # Reveal B's secrets
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Set the deprecation switch to true
    call_and_transact(token_network.functions.deprecate(), {"from": controller})
    assert token_network.functions.safety_deprecation_switch().call() is True

    # We need to make sure we can still close, settle & unlock the channels
    close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)
    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)

    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    # Unlock B's pending transfers that were sent to A
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, A, B, pending_transfers_tree_B.packed_transfers
        )
    )

    # Unlock A's pending transfers that were sent to B
    call_and_transact(
        token_network.functions.unlock(
            channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
        )
    )

    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 107
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 93
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract
