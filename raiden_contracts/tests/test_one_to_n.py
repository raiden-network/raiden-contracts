from typing import Callable, List

import pytest
from eth_tester.exceptions import TransactionFailed
from eth_typing.evm import HexAddress
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import OneToNEvent
from raiden_contracts.utils.proofs import sign_one_to_n_iou


@pytest.fixture
def make_iou(web3: Web3, one_to_n_contract: Contract, get_private_key: Callable) -> Callable:
    chain_id = int(web3.version.network)

    def f(
        sender: HexAddress,
        receiver: HexAddress,
        amount: int = 10,
        expiration_block: int = None,
        chain_id: int = chain_id,
        one_to_n_address: HexAddress = one_to_n_contract.address,
    ) -> dict:
        if expiration_block is None:
            expiration_block = web3.eth.blockNumber + 10
        iou = dict(
            sender=sender,
            receiver=receiver,
            amount=amount,
            expiration_block=expiration_block,
            one_to_n_address=one_to_n_address,
            chain_id=chain_id,
        )
        iou["signature"] = sign_one_to_n_iou(get_private_key(sender), **iou)
        del iou["chain_id"]
        return iou

    return f


def test_claim(
    user_deposit_contract: Contract,
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    web3: Web3,
    event_handler: Callable,
    make_iou: Callable,
) -> None:
    ev_handler = event_handler(one_to_n_contract)
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 30)

    # IOU expired
    with pytest.raises(TransactionFailed):
        bad_expiration = web3.eth.blockNumber - 1
        one_to_n_contract.functions.claim(
            **make_iou(sender=A, receiver=B, expiration_block=bad_expiration)
        ).call({"from": A})

    # Wrong OneToN address
    with pytest.raises(TransactionFailed):
        one_to_n_contract.functions.claim(
            **make_iou(sender=A, receiver=B, one_to_n_address=A)
        ).call({"from": A})

    # Wrong chain_id
    with pytest.raises(TransactionFailed):
        one_to_n_contract.functions.claim(**make_iou(sender=A, receiver=B, chain_id=77)).call(
            {"from": A}
        )

    # bad signature
    with pytest.raises(TransactionFailed):
        iou = make_iou(sender=A, receiver=B, amount=10)
        iou2 = make_iou(sender=A, receiver=B, amount=11)
        iou["signature"] = iou2["signature"]  # use signature for wrong amount
        one_to_n_contract.functions.claim(**iou).call({"from": A})

    # happy case
    iou = make_iou(sender=A, receiver=B)
    tx_hash = one_to_n_contract.functions.claim(**iou).call_and_transact({"from": A})

    ev_handler.assert_event(
        tx_hash,
        OneToNEvent.CLAIMED,
        dict(
            sender=A,
            receiver=B,
            expiration_block=iou["expiration_block"],
            transferred=iou["amount"],
        ),
    )
    assert user_deposit_contract.functions.balances(A).call() == 20
    assert user_deposit_contract.functions.balances(B).call() == 10

    # can't be claimed twice
    with pytest.raises(TransactionFailed):
        one_to_n_contract.functions.claim(**iou).call({"from": A})


def test_bulk_claim_happy_path(
    user_deposit_contract: Contract,
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    make_iou: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_to_udc(A, 30)
    deposit_to_udc(B, 30)

    def bulk_claim(ious: List[dict]) -> str:
        return one_to_n_contract.functions.bulkClaim(
            senders=[x["sender"] for x in ious],
            receivers=[x["receiver"] for x in ious],
            amounts=[x["amount"] for x in ious],
            expiration_blocks=[x["expiration_block"] for x in ious],
            one_to_n_address=one_to_n_contract.address,
            signatures=b"".join(x["signature"] for x in ious),
        ).call_and_transact({"from": A})

    ious = [make_iou(A, C, amount=10), make_iou(B, C, amount=20)]
    bulk_claim(ious)

    assert user_deposit_contract.functions.balances(A).call() == 20
    assert user_deposit_contract.functions.balances(B).call() == 10
    assert user_deposit_contract.functions.balances(C).call() == 30


def test_bulk_claim_errors(
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    make_iou: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_to_udc(A, 30)
    deposit_to_udc(B, 30)

    ious = [make_iou(A, C), make_iou(B, C)]
    senders = [x["sender"] for x in ious]
    receivers = [x["receiver"] for x in ious]
    amounts = [x["amount"] for x in ious]
    expiration_blocks = [x["expiration_block"] for x in ious]
    signatures = b"".join(x["signature"] for x in ious)

    # One value too many to `amounts`
    with pytest.raises(TransactionFailed):
        return one_to_n_contract.functions.bulkClaim(
            senders=senders,
            receivers=receivers,
            amounts=amounts + [1],
            expiration_blocks=expiration_blocks,
            one_to_n_address=one_to_n_contract.address,
            signatures=signatures,
        ).call_and_transact({"from": A})

    # One byte too few/many in `signatures`
    for sig in [signatures + b"1", signatures[:-1]]:
        with pytest.raises(TransactionFailed):
            return one_to_n_contract.functions.bulkClaim(
                senders=senders,
                receivers=receivers,
                amounts=amounts,
                expiration_blocks=expiration_blocks,
                one_to_n_address=one_to_n_contract.address,
                signatures=sig,
            ).call_and_transact({"from": A})

    # Cause a signature mismatch by changing one amount
    with pytest.raises(TransactionFailed):
        return one_to_n_contract.functions.bulkClaim(
            senders=senders,
            receivers=receivers,
            amounts=[amounts[0], amounts[1] + 1],
            expiration_blocks=expiration_blocks,
            one_to_n_address=one_to_n_contract.address,
            signatures=signatures,
        ).call_and_transact({"from": A})


def test_getSingleSignature(one_to_n_contract: Contract) -> None:
    signatures = bytes(range(65 * 3))
    assert one_to_n_contract.functions.getSingleSignature(signatures, 0).call() == signatures[:65]
    assert (
        one_to_n_contract.functions.getSingleSignature(signatures, 1).call()
        == signatures[65 : 65 * 2]
    )
    assert (
        one_to_n_contract.functions.getSingleSignature(signatures, 2).call()
        == signatures[65 * 2 : 65 * 3]
    )


def test_claim_with_insufficient_deposit(
    user_deposit_contract: Contract,
    one_to_n_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    get_private_key: Callable,
    web3: Web3,
    event_handler: Callable,
) -> None:
    ev_handler = event_handler(one_to_n_contract)
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 6)
    chain_id = int(web3.version.network)

    amount = 10
    expiration = web3.eth.blockNumber + 1
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration_block=expiration,
        one_to_n_address=one_to_n_contract.address,
        chain_id=chain_id,
    )

    # amount is 10, but only 6 are in deposit
    # check return value (transactions don't give back return values, so use call)
    assert (
        one_to_n_contract.functions.claim(
            A, B, amount, expiration, one_to_n_contract.address, signature
        ).call({"from": A})
        == 6
    )
    # check that transaction succeeds
    one_to_n_contract.functions.claim(
        A, B, amount, expiration, one_to_n_contract.address, signature
    ).call_and_transact({"from": A})

    assert user_deposit_contract.functions.balances(A).call() == 0
    assert user_deposit_contract.functions.balances(B).call() == 6

    # claim can be retried when transferred amount was 0
    expiration = web3.eth.blockNumber + 10
    signature = sign_one_to_n_iou(
        get_private_key(A),
        sender=A,
        receiver=B,
        amount=amount,
        expiration_block=expiration,
        one_to_n_address=one_to_n_contract.address,
        chain_id=chain_id,
    )
    one_to_n_contract.functions.claim(
        A, B, amount, expiration, one_to_n_contract.address, signature
    ).call_and_transact({"from": A})
    deposit_to_udc(A, 6 + 4)
    tx_hash = one_to_n_contract.functions.claim(
        A, B, amount, expiration, one_to_n_contract.address, signature
    ).call_and_transact({"from": A})
    ev_handler.assert_event(
        tx_hash,
        OneToNEvent.CLAIMED,
        dict(sender=A, receiver=B, expiration_block=expiration, transferred=4),
    )
