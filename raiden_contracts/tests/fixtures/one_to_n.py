from typing import Callable

import pytest
from eth_typing.evm import HexAddress
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_ONE_TO_N
from raiden_contracts.utils.proofs import sign_one_to_n_iou


@pytest.fixture(scope="session")
def one_to_n_contract(
    deploy_tester_contract: Callable,
    uninitialized_user_deposit_contract: Contract,
    web3: Web3,
    service_registry: Contract,
) -> Contract:
    chain_id = web3.eth.chain_id
    return deploy_tester_contract(
        CONTRACT_ONE_TO_N,
        _deposit_contract=uninitialized_user_deposit_contract.address,
        _chain_id=chain_id,
        _service_registry_contract=service_registry.address,
    )


@pytest.fixture(scope="session")
def one_to_n_internals(
    deploy_tester_contract: Callable,
    uninitialized_user_deposit_contract: Contract,
    web3: Web3,
    service_registry: Contract,
) -> Contract:
    chain_id = web3.eth.chain_id
    return deploy_tester_contract(
        "OneToNInternalsTest",
        _deposit_contract=uninitialized_user_deposit_contract.address,
        _chain_id=chain_id,
        _service_registry_contract=service_registry.address,
    )


@pytest.fixture
def make_iou(web3: Web3, one_to_n_contract: Contract, get_private_key: Callable) -> Callable:
    chain_id = web3.eth.chain_id

    def f(
        sender: HexAddress,
        receiver: HexAddress,
        amount: int = 10,
        expiration_block: int = None,
        chain_id: int = chain_id,
        one_to_n_address: HexAddress = one_to_n_contract.address,
    ) -> dict:
        if expiration_block is None:
            expiration_block = web3.eth.block_number + 10
        iou = dict(
            sender=sender,
            receiver=receiver,
            amount=amount,
            expiration_block=expiration_block,
            one_to_n_address=one_to_n_address,
            chain_id=chain_id,
        )
        iou["signature"] = sign_one_to_n_iou(get_private_key(sender), **iou)  # type: ignore
        del iou["chain_id"]
        del iou["one_to_n_address"]
        return iou

    return f
