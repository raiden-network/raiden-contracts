import pytest
from raiden_contracts.constants import ChannelEvent
from raiden_contracts.utils.events import check_channel_closed
from raiden_contracts.utils.sign import sign_reward_proof
from raiden_contracts.utils.merkle import EMPTY_MERKLE_ROOT


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


@pytest.mark.skip(reason='Monitoring Service implementation delayed to another milestone')
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
):
    # setup: two parties + MS
    ev_handler = event_handler(token_network)
    (A, B, MS) = get_accounts(3)
    reward_amount = 10
    # mint some tokens
    custom_token.functions.mint(50).transact({'from': MS})
    custom_token.functions.mint(50).transact({'from': A})
    custom_token.functions.mint(50).transact({'from': B})
    # register MS in the RaidenServiceBundle contract
    custom_token.functions.approve(raiden_service_bundle.address, 20).transact({'from': MS})
    raiden_service_bundle.functions.deposit(20).transact({'from': MS})
    ms_balance_after_deposit = monitoring_service_external.functions.balances(MS).call()
    # raiden node deposit
    custom_token.functions.approve(monitoring_service_external.address, 20).transact({'from': B})
    monitoring_service_external.functions.deposit(B, 20).transact({'from': B})

    # 1) open a channel (c1, c2)
    channel_identifier = create_channel(A, B)[0]
    txn_hash = channel_deposit(A, 20, B)
    txn_hash = channel_deposit(B, 20, A)
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
    txn_hash = token_network.functions.closeChannel(B, *balance_proof_A).transact({'from': A})
    ev_handler.add(txn_hash, ChannelEvent.CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()
    # 4) MS calls `MSC::monitor()` using c1's BP and reward proof

    txn_hash = monitoring_service_external.functions.monitor(
        A,
        B,
        balance_proof_B[0],  # balance_hash
        balance_proof_B[1],  # nonce
        balance_proof_B[2],  # additional_hash
        balance_proof_B[3],  # closing signature
        non_closing_signature_B,  # non-closing signature
        reward_proof[1],     # reward amount
        token_network.address,  # token network address
        reward_proof[5],      # reward proof signature
    ).transact({'from': MS})
    # 5) MSC calls TokenNetwork updateTransfer
    # 6) channel is settled
    token_network.web3.testing.mine(8)
    token_network.functions.settleChannel(
        B,                   # participant2
        10,                  # participant2_transferred_amount
        0,                   # participant2_locked_amount
        EMPTY_MERKLE_ROOT,        # participant2_locksroot
        A,                   # participant1
        20,                  # participant1_transferred_amount
        0,                   # participant1_locked_amount
        EMPTY_MERKLE_ROOT,        # participant1_locksroot
    ).transact()
    # 7) MS claims the reward
    monitoring_service_external.functions.claimReward(
        token_network.address,
        A,
        B,
    ).transact({'from': MS})
    ms_balance_after_reward = monitoring_service_external.functions.balances(MS).call()
    assert ms_balance_after_reward == (ms_balance_after_deposit + reward_amount)
