from copy import deepcopy

import pytest

from raiden_contracts.contract_manager import merge_deployment_data


def test_merge_deployment_data_identical():
    """ merge_deployment_data() throws ValueError when identical two dictionaries are given """
    deployment = {"contract_version": "0.12.0", "contracts": {"TokenNetworkRegistry": "something"}}
    with pytest.raises(ValueError):
        merge_deployment_data(deployment, deployment)  # type: ignore


def test_merge_deployment_data_wrong_chain_id():
    """ merge_deployment_data() throws ValueError on two dictionaries with different chain_id's"""
    deployment1 = {
        "chain_id": 1,
        "contract_version": "0.12.0",
        "contracts": {"TokenNetworkRegistry": "something"},
    }
    deployment2 = deepcopy(deployment1)
    deployment2["chain_id"] = 2
    deployment2["contracts"] = {"SecretRegistry": "something"}
    with pytest.raises(ValueError):
        merge_deployment_data(deployment1, deployment2)  # type: ignore
