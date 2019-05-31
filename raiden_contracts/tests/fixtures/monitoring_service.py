from typing import Callable, Tuple

import pytest
from eth_typing.evm import HexAddress
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_MONITORING_SERVICE
from raiden_contracts.utils.proofs import sign_reward_proof


@pytest.fixture(scope="session")
def monitoring_service_external(
    deploy_tester_contract: Contract,
    custom_token: Contract,
    service_registry: Contract,
    uninitialized_user_deposit_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        CONTRACT_MONITORING_SERVICE,
        [
            custom_token.address,
            service_registry.address,
            uninitialized_user_deposit_contract.address,
        ],
    )


@pytest.fixture()
def monitoring_service_internals(
    custom_token: Contract,
    service_registry: Contract,
    uninitialized_user_deposit_contract: Contract,
    deploy_tester_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        "MonitoringServiceInternalsTest",
        [
            custom_token.address,
            service_registry.address,
            uninitialized_user_deposit_contract.address,
        ],
    )


@pytest.fixture()
def create_reward_proof(token_network: Contract, get_private_key: Callable) -> Callable:
    def get(
        signer: HexAddress,
        channel_identifier: int,
        reward_amount: int,
        token_network_address: HexAddress,
        monitoring_service_contract_address: HexAddress,
        nonce: int = 0,
        v: int = 27,
    ) -> Tuple[int, int, HexAddress, int, int, bytes]:
        private_key = get_private_key(signer)

        signature = sign_reward_proof(
            private_key,
            channel_identifier,
            monitoring_service_contract_address,
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
