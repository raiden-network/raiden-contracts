import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import CONTRACTS_VERSION, OneToNEvent
from raiden_contracts.utils.proofs import sign_one_to_n_iou


def test_claim(
        user_deposit_contract,
        one_to_n_contract,
        deposit_to_udc,
        get_accounts,
        get_private_key,
        web3,
        event_handler,
):
    ev_handler = event_handler(one_to_n_contract)
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 30)

    # happy case
    amount = 10
    expiration = web3.eth.blockNumber + 2
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration=expiration,
    )
    tx_hash = one_to_n_contract.functions.claim(
        A, B, amount, expiration, signature,
    ).call_and_transact({'from': A})

    ev_handler.assert_event(
        tx_hash,
        OneToNEvent.CLAIMED,
        dict(sender=A, receiver=B, expiration_block=expiration, transferred=amount),
    )
    assert user_deposit_contract.functions.balances(A).call() == 20
    assert user_deposit_contract.functions.balances(B).call() == 10

    # can't be claimed twice
    with pytest.raises(TransactionFailed):
        one_to_n_contract.functions.claim(
            A, B, amount, expiration, signature,
        ).call({'from': A})

    # IOU expired
    with pytest.raises(TransactionFailed):
        bad_expiration = web3.eth.blockNumber + 1
        signature = sign_one_to_n_iou(
            get_private_key(A),
            sender=A,
            receiver=B,
            amount=amount,
            expiration=bad_expiration,
        )
        one_to_n_contract.functions.claim(
            A, B, amount, bad_expiration, signature,
        ).call({'from': A})

    # bad signature
    with pytest.raises(TransactionFailed):
        expiration = web3.eth.blockNumber + 1
        signature = sign_one_to_n_iou(
            get_private_key(A),
            sender=A,
            receiver=B,
            amount=amount + 1,  # this does not match amount below
            expiration=expiration,
        )
        one_to_n_contract.functions.claim(
            A, B, amount, expiration, signature,
        ).call({'from': A})


def test_claim_with_insufficient_deposit(
        user_deposit_contract,
        one_to_n_contract,
        deposit_to_udc,
        get_accounts,
        get_private_key,
        web3,
        event_handler,
):
    ev_handler = event_handler(one_to_n_contract)
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 6)

    amount = 10
    expiration = web3.eth.blockNumber + 1
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration=expiration,
    )

    # amount is 10, but only 6 are in deposit
    # check return value (transactions don't give back return values, so use call)
    assert one_to_n_contract.functions.claim(
        A, B, amount, expiration, signature,
    ).call({'from': A}) == 6
    # check that transaction succeeds
    one_to_n_contract.functions.claim(
        A, B, amount, expiration, signature,
    ).call_and_transact({'from': A})

    assert user_deposit_contract.functions.balances(A).call() == 0
    assert user_deposit_contract.functions.balances(B).call() == 6

    # claim can be retried when transferred amount was 0
    expiration = web3.eth.blockNumber + 10
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration=expiration,
    )
    one_to_n_contract.functions.claim(
        A, B, amount, expiration, signature,
    ).call_and_transact({'from': A})
    deposit_to_udc(A, 6 + 4)
    tx_hash = one_to_n_contract.functions.claim(
        A, B, amount, expiration, signature,
    ).call_and_transact({'from': A})
    ev_handler.assert_event(
        tx_hash,
        OneToNEvent.CLAIMED,
        dict(sender=A, receiver=B, expiration_block=expiration, transferred=4),
    )


def test_version(one_to_n_contract):
    """ Check the result of contract_version() call on the UserDeposit """
    version = one_to_n_contract.functions.contract_version().call()
    assert version == CONTRACTS_VERSION
