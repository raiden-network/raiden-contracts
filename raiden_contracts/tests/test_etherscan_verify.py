from raiden_contracts.contract_manager import ContractManager, contracts_source_path
from raiden_contracts.deploy.etherscan_verify import get_constructor_args


contract_name = 'DummyContract'


def test_get_constructor_args_no_args():
    contract_manager = ContractManager(contracts_source_path())
    deploy_info = {
        'contracts': {
            contract_name: {
                'constructor_arguments': [],
            },
        },
    }
    assert get_constructor_args(deploy_info, contract_name, contract_manager) == ''


def test_get_constructor_args_one_arg():
    contract_manager = ContractManager(contracts_source_path())
    contract_manager.contracts[contract_name] = {
        'abi': [
            {
                'type': 'constructor',
                'inputs': [{'type': 'uint256'}],
            },
        ],
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
    contract_manager = ContractManager(contracts_source_path())
    contract_manager.contracts[contract_name] = {
        'abi': [
            {
                'type': 'constructor',
                'inputs': [{'type': 'uint256'}, {'type': 'bool'}],
            },
        ],
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
