import pytest
from eth_abi import encode_single
from eth_tester.exceptions import TransactionFailed
from web3 import Web3

from raiden_contracts.constants import MonitoringServiceEvent
from raiden_contracts.tests.utils.constants import EMPTY_LOCKSROOT

REWARD_AMOUNT = 10


@pytest.fixture
def ms_address(
        get_accounts,
        custom_token,
        service_registry,
):
    (ms, ) = get_accounts(1)

    # register MS in the ServiceRegistry contract
    custom_token.functions.mint(50).call_and_transact({'from': ms})
    custom_token.functions.approve(service_registry.address, 20).call_and_transact({'from': ms})
    service_registry.functions.deposit(20).call_and_transact({'from': ms})

    return ms


@pytest.fixture
def monitor_data(
        get_accounts,
        deposit_to_udc,
        create_channel,
        create_balance_proof,
        create_balance_proof_update_signature,
        create_reward_proof,
        token_network,
        ms_address,
):
    # Create two parties and a channel between them
    (A, B) = get_accounts(2)
    deposit_to_udc(B, REWARD_AMOUNT)
    channel_identifier = create_channel(A, B)[0]

    # Create balance proofs
    balance_proof_A = create_balance_proof(channel_identifier, B, transferred_amount=10, nonce=1)
    balance_proof_B = create_balance_proof(channel_identifier, A, transferred_amount=20, nonce=2)

    # Add signatures by non_closing_participant
    non_closing_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_B,
    )
    reward_proof = create_reward_proof(
        B,
        channel_identifier,
        REWARD_AMOUNT,
        token_network.address,
        nonce=balance_proof_B[1],
    )

    # close channel
    token_network.functions.closeChannel(
        channel_identifier, B, *balance_proof_A,
    ).call_and_transact({'from': A})

    # return args for `monitor` function
    return {
        'participants': (A, B),
        'balance_proof_A': balance_proof_A,
        'balance_proof_B': balance_proof_B,
        'non_closing_signature': non_closing_signature_B,
        'reward_proof_signature': reward_proof[5],
        'channel_identifier': channel_identifier,
    }


def test_claimReward_with_settle_call(
        token_network,
        monitoring_service_external,
        user_deposit_contract,
        event_handler,
        monitor_data,
        ms_address,
):
    A, B = monitor_data['participants']
    channel_identifier = monitor_data['channel_identifier']

    # MS updates closed channel on behalf of B
    txn_hash = monitoring_service_external.functions.monitor(
        A, B,
        *monitor_data['balance_proof_B'],
        monitor_data['non_closing_signature'],
        REWARD_AMOUNT,
        token_network.address,
        monitor_data['reward_proof_signature'],
    ).call_and_transact({'from': ms_address})

    # claiming before settlement timeout must fail
    with pytest.raises(TransactionFailed):
        monitoring_service_external.functions.claimReward(
            channel_identifier,
            token_network.address,
            A, B,
        ).call({'from': ms_address})

    # Settle channel after settle_timeout elapsed
    token_network.web3.testing.mine(8)
    token_network.functions.settleChannel(
        channel_identifier,
        B,                   # participant_B
        10,                  # participant_B_transferred_amount
        0,                   # participant_B_locked_amount
        EMPTY_LOCKSROOT,     # participant_B_locksroot
        A,                   # participant_A
        20,                  # participant_A_transferred_amount
        0,                   # participant_A_locked_amount
        EMPTY_LOCKSROOT,     # participant_A_locksroot
    ).call_and_transact()

    # Claim reward for MS
    monitoring_service_external.functions.claimReward(
        channel_identifier,
        token_network.address,
        A, B,
    ).call_and_transact({'from': ms_address})

    # Check REWARD_CLAIMED event
    reward_identifier = Web3.sha3(
        encode_single('uint256', channel_identifier) +
        Web3.toBytes(hexstr=token_network.address),
    )
    ms_ev_handler = event_handler(monitoring_service_external)
    ms_ev_handler.assert_event(
        txn_hash,
        MonitoringServiceEvent.REWARD_CLAIMED,
        dict(
            ms_address=ms_address,
            amount=REWARD_AMOUNT,
            reward_identifier=reward_identifier,
        ),
    )

    # Check that MS balance has increased by claiming the reward
    ms_balance_after_reward = user_deposit_contract.functions.balances(ms_address).call()
    assert ms_balance_after_reward == REWARD_AMOUNT


def test_claimReward_without_settle_call(
        token_network,
        monitoring_service_external,
        user_deposit_contract,
        event_handler,
        monitor_data,
        ms_address,
):
    A, B = monitor_data['participants']
    channel_identifier = monitor_data['channel_identifier']

    # MS updates closed channel on behalf of B
    txn_hash = monitoring_service_external.functions.monitor(
        A, B,
        *monitor_data['balance_proof_B'],
        monitor_data['non_closing_signature'],
        REWARD_AMOUNT,
        token_network.address,
        monitor_data['reward_proof_signature'],
    ).call_and_transact({'from': ms_address})

    # claiming before settlement timeout must fail
    with pytest.raises(TransactionFailed):
        monitoring_service_external.functions.claimReward(
            channel_identifier,
            token_network.address,
            A, B,
        ).call({'from': ms_address})

    # Wait for settle_timeout to elapse
    token_network.web3.testing.mine(8)

    # Claim reward for MS
    monitoring_service_external.functions.claimReward(
        channel_identifier,
        token_network.address,
        A, B,
    ).call_and_transact({'from': ms_address})

    # Check REWARD_CLAIMED event
    reward_identifier = Web3.sha3(
        encode_single('uint256', channel_identifier) +
        Web3.toBytes(hexstr=token_network.address),
    )
    ms_ev_handler = event_handler(monitoring_service_external)
    ms_ev_handler.assert_event(
        txn_hash,
        MonitoringServiceEvent.REWARD_CLAIMED,
        dict(
            ms_address=ms_address,
            amount=REWARD_AMOUNT,
            reward_identifier=reward_identifier,
        ),
    )

    # Check that MS balance has increased by claiming the reward
    ms_balance_after_reward = user_deposit_contract.functions.balances(ms_address).call()
    assert ms_balance_after_reward == REWARD_AMOUNT


def test_monitor(
        token_network,
        monitoring_service_external,
        monitor_data,
        ms_address,
        event_handler,
):
    A, B = monitor_data['participants']

    # UpdateNonClosingBalanceProof is tested speparately, so we assume that all
    # parameters passed to it are handled correctly.

    # changing reward amount must lead to a failure during reward signature check
    with pytest.raises(TransactionFailed):
        txn_hash = monitoring_service_external.functions.monitor(
            A, B,
            *monitor_data['balance_proof_B'],
            monitor_data['non_closing_signature'],
            REWARD_AMOUNT + 1,
            token_network.address,
            monitor_data['reward_proof_signature'],
        ).call({'from': ms_address})

    # only registered service provicers may call `monitor`
    with pytest.raises(TransactionFailed):
        txn_hash = monitoring_service_external.functions.monitor(
            A, B,
            *monitor_data['balance_proof_B'],
            monitor_data['non_closing_signature'],
            REWARD_AMOUNT + 1,
            token_network.address,
            monitor_data['reward_proof_signature'],
        ).call({'from': B})

    # successful monitor call
    txn_hash = monitoring_service_external.functions.monitor(
        A, B,
        *monitor_data['balance_proof_B'],
        monitor_data['non_closing_signature'],
        REWARD_AMOUNT,
        token_network.address,
        monitor_data['reward_proof_signature'],
    ).call_and_transact({'from': ms_address})

    # NEW_BALANCE_PROOF_RECEIVED must get emitted
    ms_ev_handler = event_handler(monitoring_service_external)
    ms_ev_handler.assert_event(
        txn_hash,
        MonitoringServiceEvent.NEW_BALANCE_PROOF_RECEIVED,
        dict(
            token_network_address=token_network.address,
            channel_identifier=monitor_data['channel_identifier'],
            reward_amount=REWARD_AMOUNT,
            nonce=monitor_data['balance_proof_B'][1],
            ms_address=ms_address,
            raiden_node_address=B,
        ),
    )


def test_updateReward(
        monitoring_service_internals,
        ms_address,
        token_network,
        create_reward_proof,
        monitor_data,
):
    A, B = monitor_data['participants']
    reward_identifier = Web3.sha3(
        encode_single('uint256', monitor_data['channel_identifier']) +
        Web3.toBytes(hexstr=token_network.address),
    )

    def update_with_nonce(nonce):
        reward_proof = create_reward_proof(
            B,
            monitor_data['channel_identifier'],
            REWARD_AMOUNT,
            token_network.address,
            nonce=nonce,
        )
        reward_proof_signature = reward_proof[5]
        monitoring_service_internals.functions.updateRewardPublic(
            token_network.address,
            A, B,
            REWARD_AMOUNT,
            nonce,
            ms_address,
            reward_proof_signature,
        ).call_and_transact({'from': ms_address})

    # normal first call succeeds
    update_with_nonce(2)
    assert monitoring_service_internals.functions.rewardNonce(reward_identifier).call() == 2

    # calling again with same nonce fails
    with pytest.raises(TransactionFailed):
        update_with_nonce(2)

    # calling again with higher nonce succeeds
    update_with_nonce(3)
    assert monitoring_service_internals.functions.rewardNonce(reward_identifier).call() == 3
