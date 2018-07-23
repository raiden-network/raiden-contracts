import pytest
from copy import deepcopy
from random import randint
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MIN
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.fixtures.channel_test_values import channel_settle_test_values
from raiden_contracts.tests.utils import (
    get_settlement_amounts,
    get_onchain_settlement_amounts,
    get_expected_after_settlement_unlock_amounts,
    get_pending_transfers_tree,
    get_unlocked_amount,
    are_balance_proofs_valid,
    is_balance_proof_old,
)


@pytest.mark.parametrize('channel_test_values', channel_settle_test_values)
def test_channel_settle_unlock_edge_cases(
        web3,
        get_accounts,
        secret_registry_contract,
        custom_token,
        token_network,
        create_channel_and_deposit,
        withdraw_channel,
        close_and_update_channel,
        settle_state_tests,
        channel_test_values,
        reveal_secrets,
        after_settle_unlock_balance_tests,
):
    number_of_channels = 3
    accounts = get_accounts(2 * number_of_channels)
    (vals_A0, vals_B0) = channel_test_values
    all_test_cases = [(vals_A0, vals_B0)]

    # We mimic old balance proofs here, with a high locked amount and lower transferred amount
    # We expect to have the same settlement values as the original values

    def equivalent_transfers(balance_proof):
        new_balance_proof = deepcopy(balance_proof)
        new_balance_proof.locked = randint(
            balance_proof.locked,
            balance_proof.transferred + balance_proof.locked,
        )
        new_balance_proof.claimable_locked = new_balance_proof.locked
        new_balance_proof.unclaimable_locked = 0
        new_balance_proof.transferred = (
            balance_proof.transferred +
            balance_proof.locked -
            new_balance_proof.locked
        )
        return new_balance_proof

    # No reason to mimic old balance proofs if the tested values do not represent
    # valid balance proofs that are the last ones known.
    if are_balance_proofs_valid(vals_A0, vals_B0) and not is_balance_proof_old(vals_A0, vals_B0):
        print('mimic old balance proofs', vals_A0, vals_B0)
        vals_A_reversed = deepcopy(vals_A0)
        vals_A_reversed.locked = vals_A0.transferred
        vals_A_reversed.transferred = vals_A0.locked
        vals_A_reversed.claimable_locked = vals_A_reversed.locked
        vals_A_reversed.unclaimable_locked = 0

        vals_B_reversed = deepcopy(vals_B0)
        vals_B_reversed.locked = vals_B0.transferred
        vals_B_reversed.transferred = vals_B0.locked
        vals_B_reversed.claimable_locked = vals_B_reversed.locked
        vals_B_reversed.unclaimable_locked = 0

        all_test_cases.extend([
            (vals_A0, vals_B_reversed),
            (vals_A_reversed, vals_B0),
            (vals_A_reversed, vals_B_reversed),
        ] + [
            # mimicking an old balance proof for B
            sorted(
                [
                    vals_A0,
                    equivalent_transfers(vals_B0),
                ],
                key=lambda x: x.transferred + x.locked,
                reverse=False,
            ) for no in range(0, number_of_channels - 1)
        ] + [
            # mimicking an old balance proof for A
            sorted(
                [
                    equivalent_transfers(vals_A0),
                    vals_B0,
                ],
                key=lambda x: x.transferred + x.locked,
                reverse=False,
            ) for no in range(0, number_of_channels - 1)
        ] + [
            # mimicking old balance proofs for both A and B
            sorted(
                [
                    equivalent_transfers(vals_A0),
                    equivalent_transfers(vals_B0),
                ],
                key=lambda x: x.transferred + x.locked,
                reverse=False,
            ) for no in range(0, number_of_channels - 1)
        ])

    # Calculate how much A and B should receive while not knowing who will receive the
    # locked amounts
    settlement = get_settlement_amounts(vals_A0, vals_B0)
    # Calculate how much A and B receive according to onchain computation
    settlement2 = get_onchain_settlement_amounts(vals_A0, vals_B0)

    # Calculate how much A and B should receive when knowing who will receive the locked amounts
    # This is a very important check. These amounts must be equal to the final tokens received
    # after the channel lifecycle is over (after settlement & all pending transfers unlocks)
    # for all valid balance proofs. This must be true for the last known balance proofs,
    # but also for a last known balance proof + an old balance proof provided on purpose or not.
    # Where a valid balance proof is a balance proof that respects the Raiden client
    # value contraints, as defined here:
    # https://github.com/raiden-network/raiden-contracts/issues/188#issuecomment-404752095
    (
        expected_final_balance_A0,
        expected_final_balance_B0,
    ) = get_expected_after_settlement_unlock_amounts(vals_A0, vals_B0)

    for no in range(0, len(all_test_cases)):
        A = accounts[no]
        B = accounts[no + 1]
        (vals_A, vals_B) = all_test_cases[no]

        # Some checks to test that mimicking old balance proofs is done correctly
        assert vals_A.locked + vals_A.transferred == vals_A0.locked + vals_A0.transferred
        assert (
            vals_A.claimable_locked +
            vals_A.unclaimable_locked +
            vals_A.transferred
        ) == vals_A0.locked + vals_A0.transferred
        assert vals_B.locked + vals_B.transferred == vals_B0.locked + vals_B0.transferred
        assert (
            vals_B.claimable_locked +
            vals_B.unclaimable_locked +
            vals_B.transferred
        ) == vals_B0.locked + vals_B0.transferred

        # Start channel lifecycle
        create_channel_and_deposit(A, B, vals_A.deposit, vals_B.deposit)
        withdraw_channel(A, vals_A.withdrawn, B)
        withdraw_channel(B, vals_B.withdrawn, A)

        # For the purpose of this test, it is not important when the secrets are revealed,
        # as long as the secrets connected to pending transfers that should be finalized,
        # are revealed before their expiration.

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

        close_and_update_channel(
            A,
            vals_A,
            B,
            vals_B,
        )

        web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)

        pre_balance_A = custom_token.functions.balanceOf(A).call()
        pre_balance_B = custom_token.functions.balanceOf(B).call()
        pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

        call_settle(token_network, A, vals_A, B, vals_B)

        # We do the balance & state tests here for each channel and also compare with
        # the expected settlement amounts
        settle_state_tests(
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
        assert (
            settlement.participant1_balance +
            settlement.participant2_locked == settlement_equivalent.participant1_balance +
            settlement_equivalent.participant2_locked
        )
        assert (
            settlement.participant2_balance +
            settlement.participant1_locked == settlement_equivalent.participant2_balance +
            settlement_equivalent.participant1_locked
        )

        # Calculate how much A and B receive according to onchain computation
        settlement2_equivalent = get_onchain_settlement_amounts(vals_A, vals_B)
        assert (
            settlement2.participant1_balance +
            settlement2.participant2_locked == settlement2_equivalent.participant1_balance +
            settlement2_equivalent.participant2_locked
        )
        assert (
            settlement2.participant2_balance +
            settlement2.participant1_locked == settlement2_equivalent.participant2_balance +
            settlement2_equivalent.participant1_locked
        )

        assert get_unlocked_amount(
            secret_registry_contract,
            pending_transfers_tree_B.packed_transfers,
        ) == vals_B.claimable_locked

        # A unlocks B's pending transfers
        contract_locked_B = token_network.functions.getParticipantLockedAmount(
            B,
            A,
            vals_B.locksroot,
        ).call()
        if contract_locked_B == 0:
            with pytest.raises(TransactionFailed):
                token_network.functions.unlock(
                    A,
                    B,
                    pending_transfers_tree_B.packed_transfers,
                ).transact()
        else:
            token_network.functions.unlock(
                A,
                B,
                pending_transfers_tree_B.packed_transfers,
            ).transact()

            # The locked amount should have been removed from contract storage
            assert token_network.functions.getParticipantLockedAmount(
                B,
                A,
                vals_B.locksroot,
            ).call() == 0

        # B unlocks A's pending transfers
        contract_locked_A = token_network.functions.getParticipantLockedAmount(
            A,
            B,
            vals_A.locksroot,
        ).call()
        if contract_locked_A == 0:
            with pytest.raises(TransactionFailed):
                token_network.functions.unlock(
                    B,
                    A,
                    pending_transfers_tree_A.packed_transfers,
                ).transact()
        else:
            token_network.functions.unlock(
                B,
                A,
                pending_transfers_tree_A.packed_transfers,
            ).transact()

            # The locked amount should have been removed from contract storage
            assert token_network.functions.getParticipantLockedAmount(
                A,
                B,
                vals_A.locksroot,
            ).call() == 0

        # Do the post settlement and unlock tests if balance proofs are valid
        if are_balance_proofs_valid(vals_A, vals_B):
            after_settle_unlock_balance_tests(
                A,
                vals_A,
                B,
                vals_B,
                pre_balance_A,
                pre_balance_B,
                pre_balance_contract,
            )

        # Calculate how much A and B should receive after the channel is settled and
        # unlock is called by both.
        (
            expected_final_balance_A,
            expected_final_balance_B,
        ) = get_expected_after_settlement_unlock_amounts(vals_A, vals_B)

        # If the balance proofs are invalid (participants are using an unofficial malicious
        # Raiden client), there are cases where participants can lose tokens.
        # We ensure balance correctness only if both participants use the official Raiden client.
        if are_balance_proofs_valid(vals_A, vals_B):
            assert custom_token.functions.balanceOf(A).call() == (
                pre_balance_A +
                expected_final_balance_A
            )
            assert custom_token.functions.balanceOf(B).call() == (
                pre_balance_B +
                expected_final_balance_B
            )
            if are_balance_proofs_valid(vals_A0, vals_B0):
                assert expected_final_balance_A0 == expected_final_balance_A
                assert expected_final_balance_B0 == expected_final_balance_B

        # Regardless of the tokens received by the two participants, we must make sure tokens
        # are not stolen from the other channels. And we must make sure tokens are not locked in
        # the contract after the entire channel cycle is finalized.
        assert custom_token.functions.balanceOf(token_network.address).call() == (
            pre_balance_contract -
            (expected_final_balance_A + expected_final_balance_B)
        )
        assert (
            expected_final_balance_A +
            expected_final_balance_B
        ) == (expected_final_balance_A0 + expected_final_balance_B0)
