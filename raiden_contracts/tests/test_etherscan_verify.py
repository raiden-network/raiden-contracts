from typing import Dict, List

from raiden_contracts.constants import (
    CONTRACT_ENDPOINT_REGISTRY,
    CONTRACT_MONITORING_SERVICE,
    CONTRACT_ONE_TO_N,
    CONTRACT_SECRET_REGISTRY,
    CONTRACT_SERVICE_REGISTRY,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    CONTRACT_USER_DEPOSIT,
)
from raiden_contracts.contract_manager import ContractManager, contracts_source_path
from raiden_contracts.deploy.etherscan_verify import (
    get_constructor_args,
    join_sources,
    post_data_for_etherscan_verification,
)


contract_name = 'DummyContract'


def test_get_constructor_args_no_args():
    """ Test get_constructor_args() on no arguments """
    contract_manager = ContractManager(contracts_source_path())
    deploy_info: Dict = {
        'contracts': {
            contract_name: {
                'constructor_arguments': [],
            },
        },
    }
    assert get_constructor_args(deploy_info, contract_name, contract_manager) == ''


def abi_with_constructor_input_types(types: List[str]):
    return [{
        'type': 'constructor',
        'inputs': [{'type': ty} for ty in types],
    }]


def test_get_constructor_args_one_arg():
    """ Test get_constructor_args() on one argument """
    contract_manager = ContractManager(contracts_source_path())
    contract_manager.contracts[contract_name] = {
        'abi': abi_with_constructor_input_types(['uint256']),
    }
    deploy_info = {
        'contracts': {
            contract_name: {
                'constructor_arguments': [16],
            },
        },
    }
    assert get_constructor_args(deploy_info, contract_name, contract_manager) == \
        '0000000000000000000000000000000000000000000000000000000000000010'


def test_get_constructor_args_two_args():
    """ Test get_constructor_args() on two arguments """
    contract_manager = ContractManager(contracts_source_path())
    contract_manager.contracts[contract_name] = {
        'abi': abi_with_constructor_input_types(['uint256', 'bool']),
    }
    deploy_info = {
        'contracts': {
            contract_name: {
                'constructor_arguments': [16, True],
            },
        },
    }
    assert get_constructor_args(deploy_info, contract_name, contract_manager) == \
        '0000000000000000000000000000000000000000000000000000000000000010' \
        '0000000000000000000000000000000000000000000000000000000000000001'


def test_post_data_for_etherscan_verification():
    output = post_data_for_etherscan_verification(
        apikey='jkl;jkl;jkl;',
        deployment_info={'address': 'dummy_address'},
        source='dummy_source',
        contract_name=contract_name,
        metadata={
            'compiler': {
                'version': '1.2.3',
            },
            'settings': {'optimizer': {
                'enabled': False,
                'runs': 'runs',
            }},
        },
        constructor_args='constructor_arguments',
    )
    assert output == {
        'apikey': 'jkl;jkl;jkl;',
        'module': 'contract',
        'action': 'verifysourcecode',
        'contractaddress': 'dummy_address',
        'sourceCode': 'dummy_source',
        'contractname': contract_name,
        'compilerversion': 'v1.2.3',
        'optimizationUsed': 0,
        'runs': 'runs',
        'constructorArguements': 'constructor_arguments',
    }


def test_run_join_contracts():
    """ Just running join_sources() """
    join_sources('raiden', CONTRACT_TOKEN_NETWORK_REGISTRY)
    join_sources('raiden', CONTRACT_SECRET_REGISTRY)
    join_sources('raiden', CONTRACT_ENDPOINT_REGISTRY)
    join_sources('services', CONTRACT_MONITORING_SERVICE)
    join_sources('services', CONTRACT_SERVICE_REGISTRY)
    join_sources('services', CONTRACT_ONE_TO_N)
    join_sources('services', CONTRACT_USER_DEPOSIT)
