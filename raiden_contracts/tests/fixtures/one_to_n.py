import pytest

from raiden_contracts.constants import CONTRACT_ONE_TO_N


@pytest.fixture
def one_to_n_contract(
    deploy_tester_contract,
    user_deposit_contract,
):
    return deploy_tester_contract(
        CONTRACT_ONE_TO_N,
        {},
        [user_deposit_contract.address],
    )
