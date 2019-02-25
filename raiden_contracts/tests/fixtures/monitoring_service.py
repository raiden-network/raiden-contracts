import pytest
from raiden_contracts.constants import CONTRACT_MONITORING_SERVICE
from raiden_contracts.utils.proofs import sign_reward_proof


@pytest.fixture()
def get_monitoring_service(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            CONTRACT_MONITORING_SERVICE,
            {},
            arguments,
        )
    return get


@pytest.fixture()
def monitoring_service_external(
    get_monitoring_service,
    custom_token,
    service_registry,
    uninitialized_user_deposit_contract,
):
    return get_monitoring_service([
        custom_token.address,
        service_registry.address,
        uninitialized_user_deposit_contract.address,
    ])


@pytest.fixture()
def monitoring_service_internals(
    custom_token,
    service_registry,
    uninitialized_user_deposit_contract,
    deploy_tester_contract,
):
    return deploy_tester_contract(
        'MonitoringServiceInternalsTest',
        {},
        [
            custom_token.address,
            service_registry.address,
            uninitialized_user_deposit_contract.address,
        ],
    )


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
