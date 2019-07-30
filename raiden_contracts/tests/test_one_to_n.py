from typing import Callable

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
