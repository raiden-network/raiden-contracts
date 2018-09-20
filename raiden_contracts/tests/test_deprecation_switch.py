import pytest
from eth_tester.exceptions import TransactionFailed
from web3.contract import get_event_data
from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_TOKEN_NETWORK,
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)
from raiden_contracts.utils.utils import get_pending_transfers_tree
from raiden_contracts.tests.utils import ChannelValues
from raiden_contracts.tests.fixtures.channel import call_settle


def test_deprecation_executor(
        web3,
        contracts_manager,
        deploy_contract,
        secret_registry_contract,
        custom_token,
        get_accounts,
):
    (deprecation_executor, B) = get_accounts(2)

    json_contract = contracts_manager.get_contract(CONTRACT_TOKEN_NETWORK_REGISTRY)
    token_network_registry = deploy_contract(
        web3,
        deprecation_executor,
        json_contract['abi'],
        json_contract['bin'],
        [
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )

    # Make sure deployer is deprecation_executor
    assert token_network_registry.functions.deprecation_executor().call() == deprecation_executor
    assert token_network_registry.functions.token_network_created().call() is False

    # We can only deploy one TokenNetwork contract
    # It can be deployed by anyone
    tx_hash = token_network_registry.functions.createERC20TokenNetwork(
        custom_token.address,
    ).transact(
        {'from': B},
    )
    assert token_network_registry.functions.token_network_created().call() is True

    # No other TokenNetworks can be deployed now
    with pytest.raises(TransactionFailed):
        token_network_registry.functions.createERC20TokenNetwork(
            custom_token.address,
        ).transact(
            {'from': B},
        )
    with pytest.raises(TransactionFailed):
        token_network_registry.functions.createERC20TokenNetwork(
            custom_token.address,
        ).transact(
            {'from': deprecation_executor},
        )

    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    event_abi = contracts_manager.get_event_abi(
        CONTRACT_TOKEN_NETWORK_REGISTRY,
        EVENT_TOKEN_NETWORK_CREATED,
    )
    event_data = get_event_data(event_abi, tx_receipt['logs'][0])
    token_network_address = event_data['args']['token_network_address']
    token_network = web3.eth.contract(
        abi=contracts_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK),
        address=token_network_address,
    )

    assert token_network.functions.deprecation_executor().call() == deprecation_executor


def test_set_deprecation_switch(get_accounts, token_network):
    (A) = get_accounts(1)[0]
    deprecation_executor = token_network.functions.deprecation_executor().call()

    assert token_network.functions.safety_deprecation_switch().call() is False

    with pytest.raises(TransactionFailed):
        token_network.functions.deprecate().transact({
            'from': A,
        })

    token_network.functions.deprecate().transact({
        'from': deprecation_executor,
    })
    assert token_network.functions.safety_deprecation_switch().call() is True

    # We should not be able to call it again
    with pytest.raises(TransactionFailed):
        token_network.functions.deprecate().transact({
            'from': A,
        })


def test_deprecation_switch(get_accounts, token_network, create_channel, channel_deposit):
    deprecation_executor = token_network.functions.deprecation_executor().call()
    (A, B, C, D) = get_accounts(4)
    deposit = 100
    bigger_deposit = 200

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit, B)
    channel_deposit(channel_identifier, B, deposit, A)

    token_network.functions.deprecate().transact({
        'from': deprecation_executor,
    })
    assert token_network.functions.safety_deprecation_switch().call() is True

    # Now we cannot deposit in existent channels
    with pytest.raises(TransactionFailed):
        channel_deposit(channel_identifier, A, bigger_deposit, B)
    with pytest.raises(TransactionFailed):
        channel_deposit(channel_identifier, B, bigger_deposit, A)

    # Now we cannot open channels anymore
    with pytest.raises(TransactionFailed):
        channel_identifier = create_channel(C, D)[0]


def test_deprecation_switch_settle(
        web3,
        get_accounts,
        token_network,
        custom_token,
        reveal_secrets,
        create_channel,
        channel_deposit,
        close_and_update_channel,
):
    deprecation_executor = token_network.functions.deprecation_executor().call()
    (A, B) = get_accounts(2)
    deposit = 100

    (vals_A, vals_B) = (
        ChannelValues(
            deposit=deposit,
            withdrawn=0,
            transferred=5,
            claimable_locked=2,
            unclaimable_locked=4,
        ),
        ChannelValues(
            deposit=deposit,
            withdrawn=0,
            transferred=10,
            claimable_locked=4,
            unclaimable_locked=6,
        ),
    )

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, vals_A.deposit, B)
    channel_deposit(channel_identifier, B, vals_B.deposit, A)

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree(
        web3,
        unlockable_amount=vals_A.claimable_locked,
        expired_amount=vals_A.unclaimable_locked,
    )
    vals_A.locksroot = pending_transfers_tree_A.merkle_root
    # Reveal A's secrets.
    reveal_secrets(A, pending_transfers_tree_A.unlockable)

    # Mock pending transfers data for B -> A
    pending_transfers_tree_B = get_pending_transfers_tree(
        web3,
        unlockable_amount=vals_B.claimable_locked,
        expired_amount=vals_B.unclaimable_locked,
    )
    vals_B.locksroot = pending_transfers_tree_B.merkle_root
    # Reveal B's secrets
    reveal_secrets(B, pending_transfers_tree_B.unlockable)

    # Set the deprecation switch to true
    token_network.functions.deprecate().transact({
        'from': deprecation_executor,
    })
    assert token_network.functions.safety_deprecation_switch().call() is True

    # We need to make sure we can still close, settle & unlock the channels
    close_and_update_channel(
        channel_identifier,
        A,
        vals_A,
        B,
        vals_B,
    )
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)

    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    # Unlock B's pending transfers that were sent to A
    token_network.functions.unlock(
        channel_identifier,
        A,
        B,
        pending_transfers_tree_B.packed_transfers,
    ).transact()

    # Unlock A's pending transfers that were sent to B
    token_network.functions.unlock(
        channel_identifier,
        B,
        A,
        pending_transfers_tree_A.packed_transfers,
    ).transact()

    assert custom_token.functions.balanceOf(A).call() == pre_balance_A + 107
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B + 93
    assert custom_token.functions.balanceOf(
        token_network.address,
    ).call() == pre_balance_contract
