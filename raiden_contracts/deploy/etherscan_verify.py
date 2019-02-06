import json
import click
import requests
import subprocess
from time import sleep
from os import chdir
from pathlib import Path

from eth_abi import encode_abi

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
)
from raiden_contracts.contract_manager import (
    ContractManager,
    contracts_precompiled_path,
    contracts_source_path,
    get_contracts_deployed,
)


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
def etherscan_verify(chain_id, apikey, guid, contract_name):
    if guid:
        guid_status(api_of_chain_id(chain_id), guid)
        return

    if contract_name is None or contract_name == CONTRACT_ENDPOINT_REGISTRY:
        etherscan_verify_contract(chain_id, apikey, 'raiden', CONTRACT_ENDPOINT_REGISTRY)

    if contract_name is None or contract_name == CONTRACT_SECRET_REGISTRY:
        etherscan_verify_contract(chain_id, apikey, 'raiden', CONTRACT_SECRET_REGISTRY)

    if contract_name is None or contract_name == CONTRACT_TOKEN_NETWORK_REGISTRY:
        etherscan_verify_contract(chain_id, apikey, 'raiden', CONTRACT_TOKEN_NETWORK_REGISTRY)


def api_of_chain_id(chain_id):
    if chain_id == 3:
        return 'https://api-ropsten.etherscan.io/api'
    elif chain_id == 4:
        return 'https://api-rinkeby.etherscan.io/api'
    elif chain_id == 42:
        return 'https://api-kovan.etherscan.io/api'
    elif chain_id == 1:
        return 'https://api.etherscan.io/api'
    else:
        raise ValueError(
            "Unknown chain_id {chain_id}",
            err=True,
        )


def join_sources(source_module, contract_name):
    """ Use join-contracts.py to concatenate all imported Solidity files.

    Args:
        source_module: a module name to look up contracts_source_path()
        contract_name: 'TokenNetworkRegistry', 'SecretRegistry' etc.
    """
    joined_file = Path(__file__).parent.joinpath('joined.sol')

    command = [
        './utils/join-contracts.py',
        '--import-map',
        '{"raiden": "contracts", "test": "contracts/test", "services": "contracts/services"}',
        str(contracts_source_path()[source_module].joinpath(contract_name + ".sol")),
        str(joined_file),
    ]
    old_working_dir = Path.cwd()
    chdir(Path(__file__).parent.parent)
    try:
        subprocess.check_call(command)
    except subprocess.CalledProcessError as ex:
        print(f"cd {Path.cwd()}; {subprocess.list2cmdline(command)} failed.")
        raise ex
    finally:
        chdir(old_working_dir)

    return joined_file.read_text()


def get_constructor_args(deployment_info, contract_name, contract_manager):
    constructor_arguments = deployment_info['contracts'][contract_name]['constructor_arguments']
    if constructor_arguments != []:
        abi = contract_manager.contracts[contract_name]['abi']
        constructor_types = [
            arg['type'] for arg in list(
                filter(lambda x: x['type'] == 'constructor', abi),
            )[0]['inputs']
        ]
        constructor_args = encode_abi(constructor_types, constructor_arguments).hex()
    else:
        constructor_types = []
        constructor_args = ''
    print('constructor_args', constructor_arguments, constructor_types, constructor_args)
    return constructor_args


def post_data_for_etherscan_verification(
        apikey,
        deployment_info,
        source,
        contract_name,
        metadata,
        constructor_args,
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
        'constructorArguments': constructor_args,
    }
    print({k: v for k, v in data.items() if k is not 'sourceCode'})
    return data


def etherscan_verify_contract(chain_id, apikey, source_module, contract_name):
    """ Calls Etherscan API for verifying the Solidity source of a contract.

    Args:
        chain_id: EIP-155 chain id of the Ethereum chain
        apikey: key for calling Etherscan API
        source_module: a module name to look up contracts_source_path()
        contract_name: 'TokenNetworkRegistry', 'SecretRegistry' etc.
    """
    etherscan_api = api_of_chain_id(chain_id)
    deployment_info = get_contracts_deployed(chain_id)
    contract_manager = ContractManager(contracts_precompiled_path())

    data = post_data_for_etherscan_verification(
        apikey,
        deployment_info['contracts'][contract_name],
        join_sources(source_module, contract_name),
        contract_name,
        json.loads(contract_manager.contracts[contract_name]['metadata']),
        get_constructor_args(deployment_info, contract_name, contract_manager),
    )
    response = requests.post(etherscan_api, data=data)
    content = json.loads(response.content.decode())
    print(content)
    print(f'Status: {content["status"]}; {content["message"]} ; GUID = {content["result"]}')

    if content["status"] == "1":  # submission succeeded, obtained GUID
        guid = content["result"]
        status = '0'
        retries = 10
        while status == '0' and retries > 0:
            retries -= 1
            r = guid_status(etherscan_api, guid)
            status = r['status']
            if r['result'] == 'Fail - Unable to verify':
                return
            if r['result'] == 'Pass - Verified':
                return
            print('Retrying...')
            sleep(5)
        etherscan_url = etherscan_api.replace('api-', '').replace('api', '')
        etherscan_url += '/verifyContract2?a=' + data['contractaddress']
        raise TimeoutError(
            'Usually a manual submission to Etherscan works.\n' +
            'Visit ' + etherscan_url +
            '\nUse raiden_contracts/deploy/joined.sol.',
        )


def guid_status(etherscan_api, guid):
    data = {
        'guid': guid,
        'module': "contract",
        'action': "checkverifystatus",
    }
    r = requests.get(etherscan_api, data)
    status_content = json.loads(r.content.decode())
    print(status_content)
    return status_content


if __name__ == '__main__':
    etherscan_verify()
