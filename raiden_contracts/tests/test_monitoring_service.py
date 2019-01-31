import pytest
from eth_abi import encode_single
from web3 import Web3

from raiden_contracts.constants import ChannelEvent, MonitoringServiceEvent
from raiden_contracts.utils.events import (
    check_channel_closed,
    check_new_balance_proof_received,
    check_reward_claimed,
)
from raiden_contracts.utils.proofs import sign_reward_proof
from raiden_contracts.tests.utils.constants import EMPTY_LOCKSROOT


@pytest.fixture()
def create_reward_proof(token_network, get_private_key):
    def get(
            signer,
            channel_identifier,
            reward_amount,
            token_network_address,
            nonce=0,
            v=27,
    ):
        private_key = get_private_key(signer)

        signature = sign_reward_proof(
            private_key,
            channel_identifier,
            reward_amount,
            token_network_address,
            int(token_network.functions.chain_id().call()),
            nonce,
            v,
        )
        return (
            channel_identifier,
            reward_amount,
            token_network_address,
            int(token_network.functions.chain_id().call()),
            nonce,
            signature,
        )
    return get


def test_msc_happy_path(
    token_network,
    monitoring_service_external,
    get_accounts,
    create_channel,
    channel_deposit,
    create_balance_proof,
    create_balance_proof_update_signature,
    create_reward_proof,
    event_handler,
    raiden_service_bundle,
    custom_token,
    user_deposit_contract,
    deposit_to_udc,
):
    token_network_ev_handler = event_handler(token_network)
    ms_ev_handler = event_handler(monitoring_service_external)
    # setup: two parties + MS
    (A, B, MS) = get_accounts(3)
    reward_amount = 10
    deposit_to_udc(B, reward_amount)
    # register MS in the RaidenServiceBundle contract
    custom_token.functions.mint(50).transact({'from': MS})
    custom_token.functions.approve(raiden_service_bundle.address, 20).transact({'from': MS})
    raiden_service_bundle.functions.deposit(20).transact({'from': MS})

    # 1) open a channel (c1, c2)
    channel_identifier = create_channel(A, B)[0]

    # 2) create balance proof
    balance_proof_A = create_balance_proof(channel_identifier, B, transferred_amount=10, nonce=1)
    balance_proof_B = create_balance_proof(channel_identifier, A, transferred_amount=20, nonce=2)
    non_closing_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_B,
    )
    # 2a) create reward proof
    reward_proof = create_reward_proof(
        B,
        channel_identifier,
        reward_amount,
        token_network.address,
        nonce=balance_proof_B[1],
    )

    # 3) c1 closes channel
    txn_hash = token_network.functions.closeChannel(
        channel_identifier, B, *balance_proof_A,
    ).transact({'from': A})
    token_network_ev_handler.add(
        txn_hash,
        ChannelEvent.CLOSED,
        check_channel_closed(channel_identifier, A, balance_proof_A[1]),
    )
    token_network_ev_handler.check()

    # 4) MS calls `MSC::monitor()` using c1's BP and reward proof
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
    ).transact({'from': MS})
    ms_ev_handler.add(
        txn_hash,
        MonitoringServiceEvent.NEW_BALANCE_PROOF_RECEIVED,
        check_new_balance_proof_received(
            token_network.address,
            channel_identifier,
            reward_amount,
            balance_proof_B[1],
            MS,
            B,
        ),
    )
    ms_ev_handler.check()

    # 5) MSC calls TokenNetwork updateTransfer
    # 6) channel is settled
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
    ).transact()

    # 7) MS claims the reward
    monitoring_service_external.functions.claimReward(
        channel_identifier,
        token_network.address,
        A,
        B,
    ).transact({'from': MS})
    reward_identifier = Web3.sha3(
        encode_single('uint256', channel_identifier) +
        Web3.toBytes(hexstr=token_network.address),
    )
    ms_ev_handler.add(
        txn_hash,
        MonitoringServiceEvent.REWARD_CLAIMED,
        check_reward_claimed(
            MS,
            reward_amount,
            reward_identifier,
        ),
    )
    ms_ev_handler.check()
    ms_balance_after_reward = user_deposit_contract.functions.balances(MS).call()
    assert ms_balance_after_reward == reward_amount
