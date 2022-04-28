from typing import Callable, List

import pytest
from eth_tester.exceptions import TransactionFailed
from hexbytes import HexBytes
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import OneToNEvent
from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.utils.proofs import sign_one_to_n_iou
from raiden_contracts.utils.type_aliases import ChainID, TokenAmount


def test_claim(
    user_deposit_contract: Contract,
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    web3: Web3,
    event_handler: Callable,
    create_account: Callable,
    create_service_account: Callable,
    make_iou: Callable,
    get_block_timestamp: Callable,
) -> None:
    ev_handler = event_handler(one_to_n_contract)
    A = create_account()
    B = create_service_account()
    deposit_to_udc(A, 30)

    # IOU expired
    with pytest.raises(TransactionFailed, match="IOU expired"):
        bad_expiration = get_block_timestamp(web3.eth.block_number - 1)
        one_to_n_contract.functions.claim(
            *make_iou(sender=A, receiver=B, claimable_until=bad_expiration).values()
        ).call({"from": A})

    # Wrong OneToN address
    with pytest.raises(TransactionFailed, match="Signature mismatch"):
        one_to_n_contract.functions.claim(
            *make_iou(sender=A, receiver=B, one_to_n_address=A).values()
        ).call({"from": A})

    # Wrong chain_id
    with pytest.raises(TransactionFailed, match="Signature mismatch"):
        one_to_n_contract.functions.claim(
            *make_iou(sender=A, receiver=B, chain_id=77).values()
        ).call({"from": A})

    # bad signature
    with pytest.raises(TransactionFailed, match="Signature mismatch"):
        iou = make_iou(sender=A, receiver=B, amount=10)
        iou2 = make_iou(sender=A, receiver=B, amount=11)
        iou["signature"] = iou2["signature"]  # use signature for wrong amount
        one_to_n_contract.functions.claim(*iou.values()).call({"from": A})

    # happy case
    iou = make_iou(sender=A, receiver=B)
    tx_hash = call_and_transact(one_to_n_contract.functions.claim(*iou.values()), {"from": A})

    ev_handler.assert_event(
        tx_hash,
        OneToNEvent.CLAIMED,
        dict(
            sender=A,
            receiver=B,
            claimable_until=iou["claimable_until"],
            transferred=iou["amount"],
        ),
    )
    assert user_deposit_contract.functions.balances(A).call() == 20
    assert user_deposit_contract.functions.balances(B).call() == 10

    # can't be claimed twice
    with pytest.raises(TransactionFailed, match="Already settled session"):
        one_to_n_contract.functions.claim(*iou.values()).call({"from": A})


def test_bulk_claim_happy_path(
    user_deposit_contract: Contract,
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    make_iou: Callable,
    create_service_account: Callable,
) -> None:
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 30)
    deposit_to_udc(B, 30)
    C = create_service_account()

    def bulk_claim(ious: List[dict]) -> HexBytes:
        return call_and_transact(
            one_to_n_contract.functions.bulkClaim(
                senders=[x["sender"] for x in ious],
                receivers=[x["receiver"] for x in ious],
                amounts=[x["amount"] for x in ious],
                claimable_until_list=[x["claimable_until"] for x in ious],
                signatures=b"".join(x["signature"] for x in ious),
            ),
            {"from": A},
        )

    ious = [make_iou(A, C, amount=10), make_iou(B, C, amount=20)]
    bulk_claim(ious)

    assert user_deposit_contract.functions.balances(A).call() == 20
    assert user_deposit_contract.functions.balances(B).call() == 10
    assert user_deposit_contract.functions.balances(C).call() == 30


def test_bulk_claim_errors(
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    create_service_account: Callable,
    make_iou: Callable,
) -> None:
    (A, B) = get_accounts(2)
    C = create_service_account()
    deposit_to_udc(A, 30)
    deposit_to_udc(B, 30)

    ious = [make_iou(A, C), make_iou(B, C)]
    senders = [x["sender"] for x in ious]
    receivers = [x["receiver"] for x in ious]
    amounts = [x["amount"] for x in ious]
    claimable_until_list = [x["claimable_until"] for x in ious]
    signatures = b"".join(x["signature"] for x in ious)

    # One value too many to `amounts`
    with pytest.raises(
        TransactionFailed,
        match="Same number of elements required for all input parameters",
    ):
        call_and_transact(
            one_to_n_contract.functions.bulkClaim(
                senders=senders,
                receivers=receivers,
                amounts=amounts + [1],
                claimable_until_list=claimable_until_list,
                signatures=signatures,
            ),
            {"from": A},
        )

    # One byte too few/many in `signatures`
    for sig in [signatures + b"1", signatures[:-1]]:
        with pytest.raises(
            TransactionFailed, match="`signatures` should contain 65 bytes per IOU"
        ):
            call_and_transact(
                one_to_n_contract.functions.bulkClaim(
                    senders=senders,
                    receivers=receivers,
                    amounts=amounts,
                    claimable_until_list=claimable_until_list,
                    signatures=sig,
                ),
                {"from": A},
            )

    # Cause a signature mismatch by changing one amount
    with pytest.raises(TransactionFailed, match="Signature mismatch"):
        call_and_transact(
            one_to_n_contract.functions.bulkClaim(
                senders=senders,
                receivers=receivers,
                amounts=[amounts[0], amounts[1] + 1],
                claimable_until_list=claimable_until_list,
                signatures=signatures,
            ),
            {"from": A},
        )


def test_getSingleSignature(one_to_n_internals: Contract) -> None:
    signatures = bytes(range(65 * 3))
    assert (
        one_to_n_internals.functions.getSingleSignaturePublic(signatures, 0).call()
        == signatures[:65]
    )
    assert (
        one_to_n_internals.functions.getSingleSignaturePublic(signatures, 1).call()
        == signatures[65 : 65 * 2]
    )
    assert (
        one_to_n_internals.functions.getSingleSignaturePublic(signatures, 2).call()
        == signatures[65 * 2 : 65 * 3]
    )


def test_claim_by_unregistered_service(
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    get_private_key: Callable,
    web3: Web3,
    get_block_timestamp: Callable,
) -> None:
    """OneToN contract should not work for an unregistered service provider."""
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 30)

    amount = TokenAmount(10)
    expiration = get_block_timestamp() + 30
    chain_id = web3.eth.chain_id

    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        claimable_until=expiration,
        one_to_n_address=one_to_n_contract.address,
        chain_id=ChainID(chain_id),
    )

    # Doesn't work because B is not registered
    with pytest.raises(TransactionFailed, match="receiver not registered"):
        call_and_transact(
            one_to_n_contract.functions.claim(
                A,
                B,
                amount,
                expiration,
                signature,
            ),
            {"from": A},
        )


def test_claim_with_insufficient_deposit(
    user_deposit_contract: Contract,
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_private_key: Callable,
    web3: Web3,
    event_handler: Callable,
    create_account: Callable,
    create_service_account: Callable,
    get_block_timestamp: Callable,
) -> None:
    ev_handler = event_handler(one_to_n_contract)
    A = create_account()
    B = create_service_account()
    deposit_to_udc(A, 6)
    chain_id = web3.eth.chain_id

    amount = TokenAmount(10)
    expiration = get_block_timestamp() + 15
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        claimable_until=expiration,
        one_to_n_address=one_to_n_contract.address,
        chain_id=ChainID(chain_id),
    )

    # amount is 10, but only 6 are in deposit
    # check return value (transactions don't give back return values, so use call)
    assert (
        one_to_n_contract.functions.claim(A, B, amount, expiration, signature).call({"from": A})
        == 6
    )
    # check that transaction succeeds
    call_and_transact(
        one_to_n_contract.functions.claim(A, B, amount, expiration, signature),
        {"from": A},
    )

    assert user_deposit_contract.functions.balances(A).call() == 0
    assert user_deposit_contract.functions.balances(B).call() == 6

    # claim can be retried when transferred amount was 0
    expiration = get_block_timestamp() + 150
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        claimable_until=expiration,
        one_to_n_address=one_to_n_contract.address,
        chain_id=ChainID(chain_id),
    )
    call_and_transact(
        one_to_n_contract.functions.claim(A, B, amount, expiration, signature),
        {"from": A},
    )
    deposit_to_udc(A, 6 + 4)
    tx_hash = call_and_transact(
        one_to_n_contract.functions.claim(A, B, amount, expiration, signature),
        {"from": A},
    )
    ev_handler.assert_event(
        tx_hash,
        OneToNEvent.CLAIMED,
        dict(sender=A, receiver=B, claimable_until=expiration, transferred=4),
    )
