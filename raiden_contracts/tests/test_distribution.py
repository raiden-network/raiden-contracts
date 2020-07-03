from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3.contract import Contract

from raiden_contracts.tests.utils import call_and_transact


def test_claim(
    custom_token: Contract,
    distribution_contract: Contract,
    create_account: Callable,
    make_claim: Callable,
) -> None:
    A = create_account()
    B = create_account()

    # Wrong chain_id
    with pytest.raises(TransactionFailed, match="Signature mismatch"):
        distribution_contract.functions.claim(**make_claim(owner=A, partner=B, chain_id=77)).call(
            {"from": A}
        )

    # bad signature
    with pytest.raises(TransactionFailed, match="Signature mismatch"):
        iou = make_claim(owner=A, partner=B, total_amount=10)
        iou2 = make_claim(owner=A, partner=B, total_amount=11)
        iou["signature"] = iou2["signature"]  # use signature for wrong amount
        distribution_contract.functions.claim(**iou).call({"from": A})

    # happy case
    assert custom_token.functions.balances(A).call() == 0
    assert custom_token.functions.balances(B).call() == 0

    iou = make_claim(owner=A, partner=B)
    call_and_transact(distribution_contract.functions.claim(**iou), {"from": A})

    assert custom_token.functions.balances(A).call() == 10
    assert custom_token.functions.balances(B).call() == 0

    with pytest.raises(TransactionFailed, match="Already claimed"):
        call_and_transact(distribution_contract.functions.claim(**iou), {"from": A})
