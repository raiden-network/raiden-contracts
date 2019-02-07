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
    contract_manager = ContractManager(contracts_precompiled_path())
    source_path = contracts_source_path()

    if chain_id == 3:
        etherscan_api = 'https://api-ropsten.etherscan.io/api'
    elif chain_id == 4:
        etherscan_api = 'https://api-rinkeby.etherscan.io/api'
    elif chain_id == 42:
        etherscan_api = 'https://api-kovan.etherscan.io/api'
    elif chain_id == 1:
        etherscan_api = 'https://api.etherscan.io/api'
    else:
        click.echo(f"Unknown chain_id {chain_id}", err=True)
        exit(1)

    deployment_info = get_contracts_deployed(chain_id)

    if guid:
        guid_status(etherscan_api, guid)
        return

    if contract_name is None or contract_name == CONTRACT_ENDPOINT_REGISTRY:
        path = source_path['raiden'].joinpath(f'{CONTRACT_ENDPOINT_REGISTRY}.sol')
        source = path.read_text()
        constructor_args = ''
        etherscan_verify_contract(
            etherscan_api,
            apikey,
            contract_manager.contracts[CONTRACT_ENDPOINT_REGISTRY],
            CONTRACT_ENDPOINT_REGISTRY,
            deployment_info['contracts'][CONTRACT_ENDPOINT_REGISTRY],
            source,
            constructor_args,
        )

    if contract_name is None or contract_name == CONTRACT_SECRET_REGISTRY:
        path = source_path['raiden'].joinpath(f'{CONTRACT_SECRET_REGISTRY}.sol')
        source = path.read_text()
        constructor_args = ''
        etherscan_verify_contract(
            etherscan_api,
            apikey,
            contract_manager.contracts[CONTRACT_SECRET_REGISTRY],
            CONTRACT_SECRET_REGISTRY,
            deployment_info['contracts'][CONTRACT_SECRET_REGISTRY],
            source,
            constructor_args,
        )

    if contract_name is None or contract_name == CONTRACT_TOKEN_NETWORK_REGISTRY:
        joined_file = Path(__file__).parent.joinpath('joined.sol')
        command = [
            './utils/join-contracts.py',
            '--import-map',
            '{"raiden": "contracts", "test": "contracts/test", "services": "contracts/services"}',
            'contracts/TokenNetworkRegistry.sol',
            str(joined_file),
        ]
        old_working_dir = Path.cwd()
        chdir(Path(__file__).parent.parent)
        try:
            combiner = subprocess.Popen(command)
            combiner.wait()
        finally:
            chdir(old_working_dir)

        source = joined_file.read_text()

        constructor_arguments = deployment_info['contracts'][
            CONTRACT_TOKEN_NETWORK_REGISTRY
        ]['constructor_arguments']
        abi = contract_manager.contracts[CONTRACT_TOKEN_NETWORK_REGISTRY]['abi']
        constructor_types = [
            arg['type'] for arg in list(
                filter(lambda x: x['type'] == 'constructor', abi),
            )[0]['inputs']
        ]
        constructor_args = encode_abi(constructor_types, constructor_arguments).hex()
        print('constructor_args', constructor_arguments, constructor_types, constructor_args)

        etherscan_verify_contract(
            etherscan_api,
            apikey,
            contract_manager.contracts[CONTRACT_TOKEN_NETWORK_REGISTRY],
            CONTRACT_TOKEN_NETWORK_REGISTRY,
            deployment_info['contracts'][CONTRACT_TOKEN_NETWORK_REGISTRY],
            source,
            constructor_args,
        )


def etherscan_verify_contract(
        etherscan_api,
        apikey,
        compiled_info,
        contract_name,
        deployment_info,
        source_code,
        constructor_args,
):
    metadata = json.loads(compiled_info['metadata'])
    data = {
        # A valid API-Key is required
        'apikey': apikey,
        # Do not change
        'module': 'contract',
        # Do not change
        'action': 'verifysourcecode',
        'contractaddress': deployment_info['address'],
        'sourceCode': source_code,
        'contractname': contract_name,
        'compilerversion': 'v' + metadata['compiler']['version'],
        # 0 = Optimization used, 1 = No Optimization
        'optimizationUsed': 0 if metadata['settings']['optimizer']['enabled'] is False else 1,
        'runs': metadata['settings']['optimizer']['runs'],
        'constructorArguments': constructor_args,
    }
    print({k: v for k, v in data.items() if k is not 'sourceCode'})

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
