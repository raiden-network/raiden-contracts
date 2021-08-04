import json
import pprint
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

import click
import requests
from click import Context
from click.exceptions import BadParameter
from eth_abi import encode_abi

from raiden_contracts.constants import CONTRACT_LIST, CONTRACT_TOKEN_NETWORK, DeploymentModule
from raiden_contracts.contract_manager import (
    ContractManager,
    DeployedContracts,
    contracts_deployed_path,
    contracts_precompiled_path,
    get_contracts_deployment_info,
)
from raiden_contracts.contract_source_manager import (
    contracts_source_path,
    contracts_source_path_of_deployment_module,
)
from raiden_contracts.utils.type_aliases import ChainID

CONTRACT_NAMES_SEPARATED = " | ".join([c.name for c in CONTRACT_LIST])
USER_AGENT = "curl/7.37.0"  # Etherscan blocks us without this user agent in some cases
MODULE_OF_CONTRACT = {contract: module for module, contract in CONTRACT_LIST}


def validate_contract_name(_ctx: Context, _param: Any, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value in {c.name for c in CONTRACT_LIST}:
        return value
    raise BadParameter(f"unknown contract name {value}")


@click.command()
@click.option("--chain-id", default=3, help="Chain id. E.g. --chain-id 3")
@click.option("--apikey", required=True, help="A valid Etherscan APIKEY is required.")
@click.option(
    "--guid",
    help="GUID from a previous verification attempt. Tries to get the submission status.",
)
@click.option(
    "--contract-name",
    default=None,
    help=f"Contract name. Options: {CONTRACT_NAMES_SEPARATED}. "
    " Default is to submit the sources of all contracts.",
    callback=validate_contract_name,
)
def etherscan_verify(
    chain_id: ChainID, apikey: str, guid: Optional[str], contract_name: Optional[str]
) -> None:
    if guid:
        guid_status(etherscan_api=api_of_chain_id[chain_id], guid=guid, apikey=apikey)
        return

    for list_entry in CONTRACT_LIST:
        if contract_name is None or contract_name == list_entry.name:
            if list_entry.name == CONTRACT_TOKEN_NETWORK:
                _verify_token_networks(chain_id, apikey)
            else:
                _verify_singleton_contract(
                    chain_id=chain_id,
                    apikey=apikey,
                    source_module=list_entry.module,
                    contract_name=list_entry.name,
                )


def _verify_token_networks(chain_id: ChainID, apikey: str) -> None:
    deployment_file_path = contracts_deployed_path(chain_id=chain_id)
    with deployment_file_path.open() as f:
        deployed_contracts_info = json.load(f)
    token_networks = deployed_contracts_info.get("token_networks", [])

    with open(contracts_precompiled_path()) as f:
        contract_dict = json.load(f)["contracts"][CONTRACT_TOKEN_NETWORK]
    metadata = json.loads(contract_dict["metadata"])
    constructor = [func for func in contract_dict["abi"] if func["type"] == "constructor"][0]
    arg_types = [arg["type"] for arg in constructor["inputs"]]
    arg_names = [arg["name"] for arg in constructor["inputs"]]

    for tn in token_networks:
        args = [tn["constructor_arguments"][arg_name] for arg_name in arg_names]
        etherscan_verify_contract(
            chain_id=chain_id,
            apikey=apikey,
            address=tn["token_network_address"],
            contract_name=CONTRACT_TOKEN_NETWORK,
            metadata=metadata,
            constructor_args=encode_abi(arg_types, args).hex(),
        )


api_of_chain_id = {
    1: "https://api.etherscan.io/api",
    3: "https://api-ropsten.etherscan.io/api",
    4: "https://api-rinkeby.etherscan.io/api",
    5: "https://api-goerli.etherscan.io/api",
    42: "https://api-kovan.etherscan.io/api",
}


def join_sources(source_module: DeploymentModule, contract_name: str) -> str:
    """Use join_contracts.py to concatenate all imported Solidity files.

    Args:
        source_module: a module name to look up contracts_source_path()
        contract_name: 'TokenNetworkRegistry', 'SecretRegistry' etc.
    """
    joined_file = Path(__file__).parent.joinpath("joined.sol")
    remapping = {
        module: str(path) for module, path in contracts_source_path(contracts_version=None).items()
    }
    command = [
        "./utils/join_contracts.py",
        "--import-map",
        json.dumps(remapping),
        str(
            contracts_source_path_of_deployment_module(source_module).joinpath(
                contract_name + ".sol"
            )
        ),
        str(joined_file),
    ]
    working_dir = Path(__file__).parent.parent
    try:
        subprocess.check_call(command, cwd=working_dir)
    except subprocess.CalledProcessError as ex:
        print(f"cd {str(working_dir)}; {subprocess.list2cmdline(command)} failed.")
        raise ex

    return joined_file.read_text()


def get_constructor_args(
    deployment_info: DeployedContracts,
    contract_name: str,
    contract_manager: ContractManager,
) -> str:
    constructor_arguments = deployment_info["contracts"][contract_name]["constructor_arguments"]
    if constructor_arguments != []:
        constructor_types = contract_manager.get_constructor_argument_types(contract_name)
        constructor_args = encode_abi(types=constructor_types, args=constructor_arguments).hex()
    else:
        constructor_types = []
        constructor_args = ""
    print("constructor_args", constructor_arguments, constructor_types, constructor_args)
    return constructor_args


def etherscan_verify_contract(
    chain_id: ChainID,
    apikey: str,
    address: str,
    contract_name: str,
    metadata: Dict,
    constructor_args: str,
) -> None:
    source = (
        join_sources(source_module=MODULE_OF_CONTRACT[contract_name], contract_name=contract_name),
    )
    optimization_details = metadata["settings"]["optimizer"].get("details")
    data = {
        # A valid API-Key is required
        "apikey": apikey,
        # Do not change
        "module": "contract",
        # Do not change
        "action": "verifysourcecode",
        "contractaddress": address,
        "sourceCode": source,
        "contractname": contract_name,
        "compilerversion": "v" + metadata["compiler"]["version"],
        # 0 = Optimization used, 1 = No Optimization
        "optimizationUsed": 0 if optimization_details is not None else 1,
        "runs": metadata["settings"]["optimizer"]["runs"],
        # Typo is intentional. Etherscan does not like the correct spelling.
        "constructorArguements": constructor_args,
    }
    pprint.pprint({k: v for k, v in data.items() if k != "sourceCode"})

    etherscan_api = api_of_chain_id[chain_id]
    response = requests.post(etherscan_api, data=data, headers={"User-Agent": USER_AGENT})
    try:
        content = response.json()
    except json.decoder.JSONDecodeError:
        print(response.text)
        raise
    print(content)
    print(f'Status: {content["status"]}; {content["message"]} ; GUID = {content["result"]}')

    etherscan_url = etherscan_api.replace("api-", "").replace("api", "")
    etherscan_url += "/verifyContract2?a=" + data["contractaddress"]
    manual_submission_guide = f"""Usually a manual submission to Etherscan works.
    Visit {etherscan_url}
    Use raiden_contracts/deploy/joined.sol."""

    if content["status"] != "1":
        if content["result"] == "Contract source code already verified":
            return
        else:
            raise ValueError(
                "Etherscan submission failed for an unknown reason\n" + manual_submission_guide
            )

    # submission succeeded, obtained GUID
    guid = content["result"]
    status = "0"
    retries = 10
    while status == "0" and retries > 0:
        retries -= 1
        r = guid_status(etherscan_api=etherscan_api, guid=guid, apikey=apikey)
        status = r["status"]
        if r["result"] == "Fail - Unable to verify":
            raise ValueError(manual_submission_guide)
        if r["result"] == "Pass - Verified":
            return
        print("Retrying...")
        time.sleep(5)
    raise TimeoutError(manual_submission_guide)


def _verify_singleton_contract(
    chain_id: ChainID,
    apikey: str,
    source_module: DeploymentModule,
    contract_name: str,
) -> None:
    """Calls Etherscan API for verifying the Solidity source of a contract.

    This function can only be used to verify contracts which are only deployed
    once. E.g. `TokenNetworkRegistry`, but not `TokenNetwork`.
    Args:
        chain_id: EIP-155 chain id of the Ethereum chain
        apikey: key for calling Etherscan API
        source_module: a module name to look up contracts_source_path()
        contract_name: 'TokenNetworkRegistry', 'SecretRegistry' etc.
    """

    deployment_info = get_contracts_deployment_info(chain_id=chain_id, module=source_module)
    assert deployment_info
    contract_manager = ContractManager(contracts_precompiled_path())
    metadata = json.loads(contract_manager.contracts[contract_name]["metadata"])
    constructor_args = get_constructor_args(
        deployment_info=deployment_info,
        contract_name=contract_name,
        contract_manager=contract_manager,
    )
    contract_deploy_info = deployment_info["contracts"][contract_name]
    etherscan_verify_contract(
        chain_id=chain_id,
        apikey=apikey,
        address=contract_deploy_info["address"],
        contract_name=contract_name,
        metadata=metadata,
        constructor_args=constructor_args,
    )


def guid_status(etherscan_api: str, guid: str, apikey: str) -> Dict:
    data = {
        "guid": guid,
        "module": "contract",
        "action": "checkverifystatus",
        "apikey": apikey,
    }
    r = requests.get(etherscan_api, data, headers={"User-Agent": USER_AGENT})
    try:
        status_content = json.loads(r.content.decode())
    except json.decoder.JSONDecodeError:
        print(r.content.decode())
        raise
    print(status_content)
    return status_content


if __name__ == "__main__":
    # pylint: disable=E1120
    etherscan_verify()
