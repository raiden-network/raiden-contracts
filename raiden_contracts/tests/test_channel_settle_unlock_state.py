from typing import Any, Callable, Dict, Tuple

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN, ParticipantInfoIndex
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.fixtures.channel_test_values import (
    channel_settle_invalid_test_values,
    channel_settle_test_values,
)
from raiden_contracts.tests.utils import (
    NONEXISTENT_LOCKSROOT,
    UINT256_MAX,
    are_balance_proofs_valid,
    call_and_transact,
    get_expected_after_settlement_unlock_amounts,
    get_onchain_settlement_amounts,
    get_settlement_amounts,
    get_total_available_deposit,
    get_unlocked_amount,
    is_balance_proof_old,
    were_balance_proofs_valid,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.pending_transfers import (
    get_pending_transfers_tree_with_generated_lists,
)


@pytest.fixture()
def test_settlement_outcome(
    web3: Web3,
    secret_registry_contract: Contract,
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    close_and_update_channel: Callable,
    settle_state_tests: Callable,
    reveal_secrets: Callable,
) -> Callable:
    def f(
        participants: Tuple,
        channel_values: Tuple,
        expected_final_balance_A0: int,
        expected_final_balance_B0: int,
    ) -> None:
        (A, B) = participants
        (vals_A, vals_B, balance_proof_type) = channel_values
        assert were_balance_proofs_valid(vals_A, vals_B)

        # Start channel lifecycle
        channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)
        withdraw_channel(channel_identifier, A, vals_A.withdrawn, UINT256_MAX, B)
        withdraw_channel(channel_identifier, B, vals_B.withdrawn, UINT256_MAX, A)

        # For the purpose of this test, it is not important when the secrets are revealed,
        # as long as the secrets connected to pending transfers that should be finalized,
        # are revealed before their expiration.

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

        close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)

        mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN)

        pre_balance_A = custom_token.functions.balanceOf(A).call()
        pre_balance_B = custom_token.functions.balanceOf(B).call()
        pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

        call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

        # We do the balance & state tests here for each channel and also compare with
        # the expected settlement amounts
        settle_state_tests(
            channel_identifier,
            A,
            vals_A,
            B,
            vals_B,
            pre_balance_A,
            pre_balance_B,
            pre_balance_contract,
        )

        # We compute again the settlement amounts here to compare with the other channel
        # settlement test values, which should be equal

        # Calculate how much A and B should receive
        settlement_equivalent = get_settlement_amounts(vals_A, vals_B)

        # Calculate how much A and B receive according to onchain computation
        settlement_onchain_equivalent = get_onchain_settlement_amounts(vals_A, vals_B)

        assert (
            settlement_equivalent.participant1_balance
            == settlement_onchain_equivalent.participant1_balance
        )
        assert (
            settlement_equivalent.participant2_balance
            == settlement_onchain_equivalent.participant2_balance
        )
        assert (
            settlement_equivalent.participant1_locked
            == settlement_onchain_equivalent.participant1_locked
        )
        assert (
            settlement_equivalent.participant2_locked
            == settlement_onchain_equivalent.participant2_locked
        )

        assert (
            get_unlocked_amount(
                secret_registry_contract, pending_transfers_tree_B.packed_transfers
            )
            == vals_B.locked_amounts.claimable_locked
        )

        # A unlocks B's pending transfers
        info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
        assert (
            settlement_equivalent.participant2_locked == info_B[ParticipantInfoIndex.LOCKED_AMOUNT]
        )

        if info_B[ParticipantInfoIndex.LOCKED_AMOUNT] == 0:
            with pytest.raises(TransactionFailed):
                token_network.functions.unlock(
                    channel_identifier, A, B, pending_transfers_tree_B.packed_transfers
                ).call()
        else:
            call_and_transact(
                token_network.functions.unlock(
                    channel_identifier, A, B, pending_transfers_tree_B.packed_transfers
                )
            )

        # The locked amount should have been removed from contract storage
        info_B = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
        assert info_B[ParticipantInfoIndex.LOCKED_AMOUNT] == 0
        assert info_B[ParticipantInfoIndex.LOCKSROOT] == NONEXISTENT_LOCKSROOT

        # B unlocks A's pending transfers
        info_A = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
        assert (
            settlement_equivalent.participant1_locked == info_A[ParticipantInfoIndex.LOCKED_AMOUNT]
        )

        if info_A[ParticipantInfoIndex.LOCKED_AMOUNT] == 0:
            with pytest.raises(TransactionFailed):
                token_network.functions.unlock(
                    channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
                ).call()
        else:
            call_and_transact(
                token_network.functions.unlock(
                    channel_identifier, B, A, pending_transfers_tree_A.packed_transfers
                )
            )

        # The locked amount should have been removed from contract storage
        info_A = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
        assert info_A[ParticipantInfoIndex.LOCKED_AMOUNT] == 0
        assert info_A[ParticipantInfoIndex.LOCKSROOT] == NONEXISTENT_LOCKSROOT

        # Do the post settlement and unlock tests for valid balance proofs
        balance_A = custom_token.functions.balanceOf(A).call()
        balance_B = custom_token.functions.balanceOf(B).call()

        # We MUST ensure balance correctness for valid last balance proofs
        if balance_proof_type == "valid":
            # Calculate how much A and B should receive after the channel is settled and
            # unlock is called by both.
            (
                expected_final_balance_A,
                expected_final_balance_B,
            ) = get_expected_after_settlement_unlock_amounts(vals_A, vals_B)
            expected_balance_A = pre_balance_A + expected_final_balance_A
            expected_balance_B = pre_balance_B + expected_final_balance_B

            assert balance_A == expected_balance_A
            assert balance_B <= expected_balance_B

        # For balance proofs where one of them is old, we need to compare with the expected
        # final balances for the valid last balance proofs
        expected_balance_A = pre_balance_A + expected_final_balance_A0
        expected_balance_B = pre_balance_B + expected_final_balance_B0

        # Tests for when B has submitted an old balance proof for A
        # A must not receive less tokens than expected with a valid last balance proof
        # B must not receive more tokens than expected with a valid last balance proof
        if balance_proof_type == "old_last":
            assert balance_A >= expected_balance_A
            assert balance_B <= expected_balance_B

        # Tests for when A has submitted an old balance proof for B
        # A must not receive more tokens than expected with a valid last balance proof
        # B must not receive less tokens than expected with a valid last balance proof
        if balance_proof_type == "last_old":
            assert balance_A <= expected_balance_A
            assert balance_B >= expected_balance_B

        # Regardless of the tokens received by the two participants, we must make sure tokens
        # are not stolen from the other channels. And we must make sure tokens are not locked in
        # the contract after the entire channel cycle is finalized.
        final_contract_balance = custom_token.functions.balanceOf(token_network.address).call()
        assert final_contract_balance == pre_balance_contract - get_total_available_deposit(
            vals_A, vals_B
        )
        assert custom_token.functions.balanceOf(token_network.address).call() == (
            pre_balance_contract - (expected_final_balance_A0 + expected_final_balance_B0)
        )

    return f


@pytest.mark.slow
@pytest.mark.parametrize("channel_test_values", channel_settle_test_values)
@pytest.mark.parametrize("tested_range", ("one_old", "both_old_1", "both_old_2"))
# This test is split in three so it does not time out on travis
def test_channel_settle_old_balance_proof_values(
    get_accounts: Callable,
    assign_tokens: Callable,
    channel_test_values: Dict[str, Any],
    create_channel_and_deposit: Callable,
    test_settlement_outcome: Callable,
    tested_range: str,
) -> None:
    """ Test the settlement implementation when both/one of the balance proofs are outdated """
    (A, B, C, D) = get_accounts(4)
    (vals_A0, vals_B0) = channel_test_values["valid_last"]
    assert are_balance_proofs_valid(vals_A0, vals_B0)
    assert not is_balance_proof_old(vals_A0, vals_B0)

    # Mint additional tokens for participants
    assign_tokens(A, 400)
    assign_tokens(B, 200)
    # We make sure the contract has more tokens than A, B will deposit
    create_channel_and_deposit(C, D, 40, 60)

    # Calculate the final expected balances after the channel lifecycle, (after settlement and
    # unlocks), when we know how the locked amounts will be distributed.
    # This is a very important check. This must be true for the last known balance proofs,
    # but also for a last known balance proof + an old balance proof provided on purpose or not.
    # Where a valid balance proof is a balance proof that respects the Raiden client
    # value contraints, as defined here:
    # https://github.com/raiden-network/raiden-contracts/issues/188#issuecomment-404752095
    (
        expected_final_balance_A0,
        expected_final_balance_B0,
    ) = get_expected_after_settlement_unlock_amounts(vals_A0, vals_B0)

    if tested_range == "one_old":

        test_settlement_outcome(
            (A, B),
            (vals_A0, vals_B0, "valid"),
            expected_final_balance_A0,
            expected_final_balance_B0,
        )

        if "old_last" in channel_test_values:
            for vals_A in channel_test_values["old_last"]:
                vals_B = vals_B0
                test_settlement_outcome(
                    (A, B),
                    (vals_A, vals_B, "old_last"),
                    expected_final_balance_A0,
                    expected_final_balance_B0,
                )

        if "last_old" in channel_test_values:
            for vals_B in channel_test_values["last_old"]:
                vals_A = vals_A0
                test_settlement_outcome(
                    (A, B),
                    (vals_A, vals_B, "last_old"),
                    expected_final_balance_A0,
                    expected_final_balance_B0,
                )

    elif tested_range == "both_old_1":

        if "old_last" in channel_test_values and "last_old" in channel_test_values:
            for vals_A in channel_test_values["old_last"][:5]:
                for vals_B in channel_test_values["last_old"][:5]:
                    # We only need to test for cases  where the we have the same argument ordering
                    # for settleChannel, keeping the order of balance calculations
                    B_total = vals_B.transferred + vals_B.locked_amounts.locked
                    A_total = vals_A.transferred + vals_A.locked_amounts.locked
                    if B_total >= A_total:
                        test_settlement_outcome(
                            (A, B),
                            (vals_A, vals_B, "invalid"),
                            expected_final_balance_A0,
                            expected_final_balance_B0,
                        )

    else:

        if "old_last" in channel_test_values and "last_old" in channel_test_values:
            for vals_A in channel_test_values["old_last"][5:]:
                for vals_B in channel_test_values["last_old"][5:]:
                    # We only need to test for cases  where the we have the same argument ordering
                    # for settleChannel, keeping the order of balance calculations
                    B_total = vals_B.transferred + vals_B.locked_amounts.locked
                    A_total = vals_A.transferred + vals_A.locked_amounts.locked
                    if B_total >= A_total:
                        test_settlement_outcome(
                            (A, B),
                            (vals_A, vals_B, "invalid"),
                            expected_final_balance_A0,
                            expected_final_balance_B0,
                        )


@pytest.mark.slow
@pytest.mark.parametrize("channel_test_values", channel_settle_invalid_test_values)
def test_channel_settle_invalid_balance_proof_values(
    web3: Web3,
    get_accounts: Callable,
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    close_and_update_channel: Callable,
    settle_state_tests: Callable,
    reveal_secrets: Callable,
    channel_test_values: Tuple,
) -> None:
    """ Check the settlement results with invalid balance proofs """
    (A, B, C, D) = get_accounts(4)
    (vals_A, vals_B) = channel_test_values

    # We just need to test that settleChannel does not fail
    # We cannot ensure correctly computed final balances if the balance proofs
    # are invalid.
    # We can just test that participants do not get more tokens than the channel deposit

    # We make sure the contract has more tokens than A, B will deposit
    create_channel_and_deposit(C, D, 40, 60)

    # Start channel lifecycle for A, B
    channel_identifier = create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)
    withdraw_channel(channel_identifier, A, vals_A.withdrawn, UINT256_MAX, B)
    withdraw_channel(channel_identifier, B, vals_B.withdrawn, UINT256_MAX, A)

    # For the purpose of this test, it is not important when the secrets are revealed,
    # as long as the secrets connected to pending transfers that should be finalized,
    # are revealed before their expiration.

    # Mock pending transfers data for A -> B
    pending_transfers_tree_A = get_pending_transfers_tree_with_generated_lists(
        web3=web3,
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

    close_and_update_channel(channel_identifier, A, vals_A, B, vals_B)

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)

    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)

    # We do the balance & state tests here for each channel and also compare with
    # the expected settlement amounts
    settle_state_tests(
        channel_identifier,
        A,
        vals_A,
        B,
        vals_B,
        pre_balance_A,
        pre_balance_B,
        pre_balance_contract,
    )
