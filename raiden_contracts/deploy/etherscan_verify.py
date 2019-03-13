import json
import pprint
import subprocess
from collections import namedtuple
from pathlib import Path
from time import sleep
from typing import Dict, Optional

import click
import requests
from eth_abi import encode_abi

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    contracts_precompiled_path,
    get_contracts_deployed,
)
from raiden_contracts.contract_source_manager import contracts_source_path

ContractListEntry = namedtuple('ContractListEntry', 'module name')

CONTRACT_LIST = [
    ContractListEntry(module='raiden', name=CONTRACT_ENDPOINT_REGISTRY),
    ContractListEntry(module='raiden', name=CONTRACT_SECRET_REGISTRY),
    ContractListEntry(module='raiden', name=CONTRACT_TOKEN_NETWORK_REGISTRY),
    ContractListEntry(module='services', name=CONTRACT_SERVICE_REGISTRY),
    ContractListEntry(module='services', name=CONTRACT_MONITORING_SERVICE),
    ContractListEntry(module='services', name=CONTRACT_ONE_TO_N),
    ContractListEntry(module='services', name=CONTRACT_USER_DEPOSIT),
]


@click.command()
@click.option(
    '--chain-id',
    default=3,
    help='Chain id. E.g. --chain-id 3',
)
@click.option(
    '--apikey',
    required=True,
    help='A valid Etherscan APIKEY is required.',
)
@click.option(
    '--guid',
    help='GUID from a previous verification attempt. Tries to get the submission status.',
)
@click.option(
    '--contract-name',
    default=None,
    help='Contract name. Options: EndpointRegistry | SecretRegistry | TokenNetworkRegistry',
)
def etherscan_verify(
        chain_id: int,
        apikey: str,
        guid: Optional[str],
        contract_name: Optional[str],
):
    if guid:
        guid_status(etherscan_api=api_of_chain_id[chain_id], guid=guid)
        return

    for list_entry in CONTRACT_LIST:
        if contract_name is None or contract_name == list_entry.name:
            etherscan_verify_contract(
                chain_id=chain_id,
                apikey=apikey,
                source_module=list_entry.module,
                contract_name=list_entry.name,
            )


api_of_chain_id = {
    1: 'https://api.etherscan.io/api',
    3: 'https://api-ropsten.etherscan.io/api',
    4: 'https://api-rinkeby.etherscan.io/api',
    42: 'https://api-kovan.etherscan.io/api',
}


def join_sources(source_module: str, contract_name: str):
    """ Use join-contracts.py to concatenate all imported Solidity files.

    Args:
        source_module: a module name to look up contracts_source_path()
        contract_name: 'TokenNetworkRegistry', 'SecretRegistry' etc.
    """
    joined_file = Path(__file__).parent.joinpath('joined.sol')
    remapping = {module: str(path) for module, path in contracts_source_path().items()}
    command = [
        './utils/join-contracts.py',
        '--import-map',
        json.dumps(remapping),
        str(contracts_source_path()[source_module].joinpath(contract_name + '.sol')),
        str(joined_file),
    ]
    working_dir = Path(__file__).parent.parent
    try:
        subprocess.check_call(command, cwd=working_dir)
    except subprocess.CalledProcessError as ex:
        print(f'cd {str(working_dir)}; {subprocess.list2cmdline(command)} failed.')
        raise ex

    return joined_file.read_text()


def get_constructor_args(
        deployment_info: Dict,
        contract_name: str,
        contract_manager: ContractManager,
):
    constructor_arguments = deployment_info['contracts'][contract_name]['constructor_arguments']
    if constructor_arguments != []:
        abi = contract_manager.contracts[contract_name]['abi']
        constructor_types = [
            arg['type'] for arg in list(
                filter(lambda x: x['type'] == 'constructor', abi),
            )[0]['inputs']
        ]
        constructor_args = encode_abi(types=constructor_types, args=constructor_arguments).hex()
    else:
        constructor_types = []
        constructor_args = ''
    print('constructor_args', constructor_arguments, constructor_types, constructor_args)
    return constructor_args


def post_data_for_etherscan_verification(
        apikey: str,
        deployment_info: Dict,
        source: str,
        contract_name: str,
        metadata: Dict,
        constructor_args: str,
):
    data = {
        # A valid API-Key is required
        'apikey': apikey,
        # Do not change
        'module': 'contract',
        # Do not change
        'action': 'verifysourcecode',
        'contractaddress': deployment_info['address'],
        'sourceCode': source,
        'contractname': contract_name,
        'compilerversion': 'v' + metadata['compiler']['version'],
        # 0 = Optimization used, 1 = No Optimization
        'optimizationUsed': 0 if metadata['settings']['optimizer']['enabled'] is False else 1,
        'runs': metadata['settings']['optimizer']['runs'],
        # Typo is intentional. Etherscan does not like the correct spelling.
        'constructorArguements': constructor_args,
    }
    pprint.pprint({k: v for k, v in data.items() if k is not 'sourceCode'})
    return data


def etherscan_verify_contract(
        chain_id: int,
        apikey: str,
        source_module: str,
        contract_name: str,
):
    """ Calls Etherscan API for verifying the Solidity source of a contract.

    Args:
        chain_id: EIP-155 chain id of the Ethereum chain
        apikey: key for calling Etherscan API
        source_module: a module name to look up contracts_source_path()
        contract_name: 'TokenNetworkRegistry', 'SecretRegistry' etc.
    """
    etherscan_api = api_of_chain_id[chain_id]
    deployment_info = get_contracts_deployed(
        chain_id=chain_id,
        services=(source_module == 'services'),
    )
    contract_manager = ContractManager(contracts_precompiled_path())

    data = post_data_for_etherscan_verification(
        apikey=apikey,
        deployment_info=deployment_info['contracts'][contract_name],
        source=join_sources(source_module, contract_name),
        contract_name=contract_name,
        metadata=json.loads(contract_manager.contracts[contract_name]['metadata']),
        constructor_args=get_constructor_args(deployment_info, contract_name, contract_manager),
    )
    response = requests.post(etherscan_api, data=data)
    content = json.loads(response.content.decode())
    print(content)
    print(f'Status: {content["status"]}; {content["message"]} ; GUID = {content["result"]}')

    etherscan_url = etherscan_api.replace('api-', '').replace('api', '')
    etherscan_url += '/verifyContract2?a=' + data['contractaddress']
    manual_submission_guide = f"""Usually a manual submission to Etherscan works.
    Visit {etherscan_url}
    Use raiden_contracts/deploy/joined.sol."""

    if content['status'] == '1':  # submission succeeded, obtained GUID
        guid = content['result']
        status = '0'
        retries = 10
        while status == '0' and retries > 0:
            retries -= 1
            r = guid_status(etherscan_api=etherscan_api, guid=guid)
            status = r['status']
            if r['result'] == 'Fail - Unable to verify':
                raise ValueError(manual_submission_guide)
            if r['result'] == 'Pass - Verified':
                return
            print('Retrying...')
            sleep(5)
        raise TimeoutError(manual_submission_guide)
    else:
        if content['result'] == 'Contract source code already verified':
            return
        else:
            raise ValueError(
                'Etherscan submission failed for an unknown reason\n' +
                manual_submission_guide,
            )


def guid_status(etherscan_api: str, guid: str):
    data = {
        'guid': guid,
        'module': 'contract',
        'action': 'checkverifystatus',
    }
    r = requests.get(etherscan_api, data)
    status_content = json.loads(r.content.decode())
    print(status_content)
    return status_content


if __name__ == '__main__':
    # pylint: disable=E1120
    etherscan_verify()
