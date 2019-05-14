from typing import Dict, List

import requests_mock
from click.testing import CliRunner

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    DeploymentModule,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    DeployedContracts,
    contracts_precompiled_path,
)
from raiden_contracts.deploy.etherscan_verify import (
    api_of_chain_id,
    etherscan_verify,
    get_constructor_args,
    guid_status,
    join_sources,
    post_data_for_etherscan_verification,
)
from raiden_contracts.utils.type_aliases import Address

contract_name = "DummyContract"


def test_get_constructor_args_no_args():
    """ Test get_constructor_args() on no arguments """
    contract_manager = ContractManager(contracts_precompiled_path())
    deploy_info: Dict = {"contracts": {contract_name: {"constructor_arguments": []}}}
    assert get_constructor_args(deploy_info, contract_name, contract_manager) == ""  # type: ignore


def abi_with_constructor_input_types(types: List[str]):
    return [{"type": "constructor", "inputs": [{"type": ty} for ty in types]}]


def test_get_constructor_args_one_arg():
    """ Test get_constructor_args() on one argument """
    contract_manager = ContractManager(contracts_precompiled_path())
    contract_manager.contracts[contract_name] = {
        "address": Address("0x00112233445566778899aabbccddeeff00112233"),
        "abi": abi_with_constructor_input_types(["uint256"]),
        "transaction_hash": "dummy",
        "gas_cost": 300,
        "constructor_arguments": ["dummy"],
        "bin": "dummy",
        "bin-runtime": "dummy",
        "metadata": "dummy",
        "block_number": 3,
    }
    deploy_info: DeployedContracts = {  # type: ignore
        "contracts": {contract_name: {"constructor_arguments": [16]}}
    }
    assert (
        get_constructor_args(deploy_info, contract_name, contract_manager)
        == "0000000000000000000000000000000000000000000000000000000000000010"
    )


def test_get_constructor_args_two_args():
    """ Test get_constructor_args() on two arguments """
    contract_manager = ContractManager(contracts_precompiled_path())
    contract_manager.contracts[contract_name] = {
        "address": Address("0x00112233445566778899aabbccddeeff00112233"),
        "abi": abi_with_constructor_input_types(["uint256", "bool"]),
        "block_number": 0,
        "bin-runtime": "dummy",
        "bin": "dummy",
        "constructor_arguments": ["dummy"],
        "metadata": "dummy",
        "gas_cost": 300,
        "transaction_hash": "dummy",
    }
    deploy_info: DeployedContracts = {  # type: ignore
        "contracts": {contract_name: {"constructor_arguments": [16, True]}}
    }
    assert (
        get_constructor_args(deploy_info, contract_name, contract_manager)
        == "0000000000000000000000000000000000000000000000000000000000000010"
        "0000000000000000000000000000000000000000000000000000000000000001"
    )


def test_post_data_for_etherscan_verification():
    output = post_data_for_etherscan_verification(
        apikey="jkl;jkl;jkl;",
        deployment_info={"address": "dummy_address"},  # type: ignore
        source="dummy_source",
        contract_name=contract_name,
        metadata={
            "compiler": {"version": "1.2.3"},
            "settings": {"optimizer": {"enabled": False, "runs": "runs"}},
        },
        constructor_args="constructor_arguments",
    )
    assert output == {
        "apikey": "jkl;jkl;jkl;",
        "module": "contract",
        "action": "verifysourcecode",
        "contractaddress": "dummy_address",
        "sourceCode": "dummy_source",
        "contractname": contract_name,
        "compilerversion": "v1.2.3",
        "optimizationUsed": 0,
        "runs": "runs",
        "constructorArguements": "constructor_arguments",
    }


def test_run_join_contracts():
    """ Just running join_sources() """
    join_sources(DeploymentModule.RAIDEN, CONTRACT_TOKEN_NETWORK_REGISTRY)
    join_sources(DeploymentModule.RAIDEN, CONTRACT_SECRET_REGISTRY)
    join_sources(DeploymentModule.RAIDEN, CONTRACT_ENDPOINT_REGISTRY)
    join_sources(DeploymentModule.SERVICES, CONTRACT_MONITORING_SERVICE)
    join_sources(DeploymentModule.SERVICES, CONTRACT_SERVICE_REGISTRY)
    join_sources(DeploymentModule.SERVICES, CONTRACT_ONE_TO_N)
    join_sources(DeploymentModule.SERVICES, CONTRACT_USER_DEPOSIT)


def test_guid_status():
    with requests_mock.Mocker() as m:
        etherscan_api = api_of_chain_id[3]
        m.get(etherscan_api, text='{ "content": 1 }')
        assert guid_status(etherscan_api, "something") == {"content": 1}


def test_etherscan_verify_with_guid():
    with requests_mock.Mocker() as m:
        chain_id = 3
        etherscan_api = api_of_chain_id[chain_id]
        m.get(etherscan_api, text='{ "content": 1 }')
        runner = CliRunner()
        result = runner.invoke(
            etherscan_verify,
            ["--chain-id", str(chain_id), "--apikey", "API", "--guid", "something"],
        )
        assert result.exit_code == 0


def test_etherscan_verify_already_verified():
    with requests_mock.Mocker() as m:
        chain_id = 3
        etherscan_api = api_of_chain_id[chain_id]
        m.post(
            etherscan_api,
            text="""
            {
                "status": "0",
                "result" : "Contract source code already verified",
                "message" : ""
            }
            """,
        )
        runner = CliRunner()
        result = runner.invoke(
            etherscan_verify,
            [
                "--chain-id",
                str(chain_id),
                "--apikey",
                "API",
                "--contract-name",
                "EndpointRegistry",
            ],
        )
        assert result.exit_code == 0


def test_etherscan_verify_unknown_error():
    with requests_mock.Mocker() as m:
        chain_id = 3
        etherscan_api = api_of_chain_id[chain_id]
        m.post(
            etherscan_api,
            text="""
            {
                "status": "0",'
                "result" : "Unknown message",
                "message" : ""
            }
            """,
        )
        runner = CliRunner()
        result = runner.invoke(
            etherscan_verify,
            [
                "--chain-id",
                str(chain_id),
                "--apikey",
                "API",
                "--contract-name",
                "EndpointRegistry",
            ],
        )
        assert result.exit_code != 0


def test_etherscan_verify_unable_to_verify():
    with requests_mock.Mocker() as m:
        chain_id = 3
        etherscan_api = api_of_chain_id[chain_id]
        m.post(
            etherscan_api,
            text="""
            {
                "status": "1",
                "result" : "dummy_guid",
                "message" : ""
            }
            """,
        )
        m.get(
            etherscan_api,
            text="""
            {
                "status": "0",
                "result" : "Fail - Unable to verify",
                "message" : ""
            }
            """,
        )
        runner = CliRunner()
        result = runner.invoke(
            etherscan_verify,
            [
                "--chain-id",
                str(chain_id),
                "--apikey",
                "API",
                "--contract-name",
                "EndpointRegistry",
            ],
        )
        assert result.exit_code != 0


def test_etherscan_verify_success():
    with requests_mock.Mocker() as m:
        chain_id = 3
        etherscan_api = api_of_chain_id[chain_id]
        m.post(etherscan_api, text='{ "status": "1", "result" : "guid", "message" : "" }')
        m.get(
            etherscan_api,
            text="""
            {
                "status": "1",
                "result" : "Pass - Verified",
                "message" : ""
            }
            """,
        )
        runner = CliRunner()
        result = runner.invoke(
            etherscan_verify,
            [
                "--chain-id",
                str(chain_id),
                "--apikey",
                "API",
                "--contract-name",
                "EndpointRegistry",
            ],
        )
        assert result.exit_code == 0


def first_fail_second_succeed(_, context):
    """ Simulate Etherscan saying for the first time 'wait', but for the second time 'success'. """
    context.status_code = 200
    try:
        if first_fail_second_succeed.called:  # type: ignore
            return '{ "status": "1", "result" : "Pass - Verified", "message" : "" }'
    except AttributeError:  # first time
        pass
    first_fail_second_succeed.called = True  # type: ignore
    return '{ "status": "0", "result" : "wait for a moment", "message" : "" }'


def test_etherscan_verify_success_after_a_loop():
    with requests_mock.Mocker() as m:
        chain_id = 3
        etherscan_api = api_of_chain_id[chain_id]
        m.post(etherscan_api, text='{ "status": "1", "result" : "guid", "message" : "" }')
        m.get(etherscan_api, text=first_fail_second_succeed)
        runner = CliRunner()
        result = runner.invoke(
            etherscan_verify,
            [
                "--chain-id",
                str(chain_id),
                "--apikey",
                "API",
                "--contract-name",
                "EndpointRegistry",
            ],
        )
        assert result.exit_code == 0
