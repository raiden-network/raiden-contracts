import pytest

from raiden_contracts.constants import CONTRACT_ONE_TO_N


@pytest.fixture(scope="session")
def one_to_n_contract(deploy_tester_contract, uninitialized_user_deposit_contract, web3):
    chain_id = int(web3.version.network)
    return deploy_tester_contract(
        CONTRACT_ONE_TO_N, [uninitialized_user_deposit_contract.address, chain_id]
    )
