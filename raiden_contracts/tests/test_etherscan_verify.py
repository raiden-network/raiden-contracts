from typing import Any, Dict, List

import requests_mock
from click.testing import CliRunner
from web3.types import ABI

from raiden_contracts.constants import (
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
    DeploymentModule,
)
from raiden_contracts.contract_manager import (
    CompiledContract,
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
)

contract_name = "DummyContract"


def test_get_constructor_args_no_args() -> None:
    """Test get_constructor_args() on no arguments"""
    contract_manager = ContractManager(contracts_precompiled_path())
    deploy_info: Dict = {"contracts": {contract_name: {"constructor_arguments": []}}}
    assert get_constructor_args(deploy_info, contract_name, contract_manager) == ""  # type: ignore


def abi_with_constructor_input_types(types: List[str]) -> ABI:
    return [{"type": "constructor", "inputs": [{"type": ty} for ty in types]}]  # type: ignore


def test_get_constructor_args_one_arg() -> None:
    """Test get_constructor_args() on one argument"""
    contract_manager = ContractManager(contracts_precompiled_path())
    contract_manager.contracts[contract_name] = CompiledContract(
        {
            "abi": abi_with_constructor_input_types(["uint256"]),
            "bin": "dummy",
            "bin-runtime": "dummy",
            "metadata": "dummy",
        }
    )
    deploy_info: DeployedContracts = {
        "contracts": {contract_name: {"constructor_arguments": [16]}}  # type: ignore
    }
    assert (
        get_constructor_args(deploy_info, contract_name, contract_manager)
        == "0000000000000000000000000000000000000000000000000000000000000010"
    )


def test_get_constructor_args_two_args() -> None:
    """Test get_constructor_args() on two arguments"""
    contract_manager = ContractManager(contracts_precompiled_path())
    contract_manager.contracts[contract_name] = CompiledContract(
        {
            "abi": abi_with_constructor_input_types(["uint256", "bool"]),
            "bin-runtime": "dummy",
            "bin": "dummy",
            "metadata": "dummy",
        }
    )
    deploy_info: DeployedContracts = {
        "contracts": {contract_name: {"constructor_arguments": [16, True]}}  # type: ignore
    }
    assert (
        get_constructor_args(deploy_info, contract_name, contract_manager)
        == "0000000000000000000000000000000000000000000000000000000000000010"
        "0000000000000000000000000000000000000000000000000000000000000001"
    )


def test_run_join_contracts() -> None:
    """Just running join_sources()"""
    join_sources(DeploymentModule.RAIDEN, CONTRACT_TOKEN_NETWORK_REGISTRY)
    join_sources(DeploymentModule.RAIDEN, CONTRACT_SECRET_REGISTRY)
    join_sources(DeploymentModule.SERVICES, CONTRACT_MONITORING_SERVICE)
    join_sources(DeploymentModule.SERVICES, CONTRACT_SERVICE_REGISTRY)
    join_sources(DeploymentModule.SERVICES, CONTRACT_ONE_TO_N)
    join_sources(DeploymentModule.SERVICES, CONTRACT_USER_DEPOSIT)


def test_guid_status() -> None:
    with requests_mock.Mocker() as m:
        etherscan_api = api_of_chain_id[3]
        m.get(etherscan_api, text='{ "content": 1 }')
        assert guid_status(etherscan_api, "something", apikey="foo") == {"content": 1}


def test_etherscan_verify_with_guid() -> None:
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


def test_etherscan_verify_already_verified() -> None:
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
        runner.invoke(
            etherscan_verify,
            [
                "--chain-id",
                str(chain_id),
                "--apikey",
                "API",
                "--contract-name",
                "SecretRegistry",
            ],
            catch_exceptions=False,
        )


def test_etherscan_verify_unknown_error() -> None:
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
                "SecretRegistry",
            ],
        )
        assert result.exit_code != 0


def test_etherscan_verify_unable_to_verify() -> None:
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
                "SecretRegistry",
            ],
        )
        assert result.exit_code != 0


def test_etherscan_verify_success() -> None:
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
                "SecretRegistry",
            ],
        )
        assert result.exit_code == 0


def first_fail_second_succeed(_: Any, context: Any) -> str:
    """Simulate Etherscan saying for the first time 'wait', but for the second time 'success'."""
    context.status_code = 200
    try:
        if first_fail_second_succeed.called:  # type: ignore
            return '{ "status": "1", "result" : "Pass - Verified", "message" : "" }'
    except AttributeError:  # first time
        pass
    first_fail_second_succeed.called = True  # type: ignore
    return '{ "status": "0", "result" : "wait for a moment", "message" : "" }'


def test_etherscan_verify_success_after_a_loop() -> None:
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
                "SecretRegistry",
            ],
        )
        assert result.exit_code == 0


def test_etherscan_verify_fail_unknown_contract() -> None:
    """When invoked with an unknown contract name, etherscan_verify should error"""
    chain_id = 3
    runner = CliRunner()
    result = runner.invoke(
        etherscan_verify,
        ["--chain-id", str(chain_id), "--apikey", "API", "--contract-name", "Unknown"],
    )
    assert result.exit_code != 0
    assert result.exception
    assert "unknown contract name" in result.output
