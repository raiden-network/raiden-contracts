import os
import json
import logging
from typing import Union, List, Dict

from solc import compile_files

log = logging.getLogger(__name__)
CONTRACTS_DIR = os.path.join(os.path.dirname(__file__), 'data/contracts.json')
CONTRACTS_SOURCE_DIRS = {
    'raiden': os.path.join(os.path.dirname(__file__), 'contracts/'),
    'test': os.path.join(os.path.dirname(__file__), 'contracts/test'),
}
CONTRACTS_SOURCE_DIRS = {
    k: os.path.normpath(v) for k, v in CONTRACTS_SOURCE_DIRS.items()
}


def get_event_from_abi(abi: List, event_name: str):
    result = [
        x for x in abi
        if x['type'] == 'event' and x['name'] == event_name
    ]

    num_results = len(result)
    if num_results == 0:
        raise KeyError("Event '{}' not found.".format(event_name))
    elif num_results >= 2:
        raise KeyError("Multiple events '{}' found.".format(event_name))

    return result[0]


def fix_contract_key_names(input: Dict) -> Dict:
    result = {}

    for k, v in input.items():
        name = k.split(':')[1]
        result[name] = v

    return result


class ContractManager:
    def __init__(self, path: Union[str, List[str]]) -> None:
        """Params:
            path: either path to a precompiled contract JSON file, or a list of
                directories which contain solidity files to compile
        """
        self.contracts_source_dirs = None
        self.abi = dict()
        if isinstance(path, dict):
            self.contracts_source_dirs = path
            for dir_path in path.values():
                self.abi.update(
                    ContractManager.precompile_contracts(dir_path, self.get_mappings())
                )
        elif os.path.isdir(path):
            ContractManager.__init__(self, [path])
        else:
            self.abi = json.load(open(path, 'r'))

    def compile_contract(self, contract_name: str, libs=None, *args):
        """Compile contract and return JSON containing abi and bytecode"""
        contract_json = compile_files(
            [self.get_contract_path(contract_name)[0]],
            output_values=('abi', 'bin', 'ast'),
            import_remappings=self.get_mappings(),
            optimize=False
        )
        contract_json = {
            os.path.basename(key).split('.', 1)[0]: value
            for key, value in contract_json.items()
        }
        return contract_json.get(contract_name, None)

    def get_contract_path(self, contract_name: str):
        return sum(
            (self.list_contract_path(contract_name, x)
             for x in self.contracts_source_dirs.values()),
            []
        )

    @staticmethod
    def list_contract_path(contract_name: str, directory: str):
        """Get contract source file for a specified contract"""
        return [
            os.path.join(directory, x)
            for x in os.listdir(directory)
            if os.path.basename(x).split('.', 1)[0] == contract_name
        ]

    def get_mappings(self) -> List[str]:
        """Return dict of mappings to use as solc argument."""
        return ['%s=%s' % (k, v) for k, v in self.contracts_source_dirs.items()]

    @staticmethod
    def precompile_contracts(contracts_dir: str, map_dirs: List) -> Dict:
        """
        Compile solidity contracts into ABI. This requires solc somewhere in the $PATH
            and also ethereum.tools python library.
        Parameters:
            contracts_dir: directory where the contracts are stored.
            All files with .sol suffix will be compiled.
            The method won't recurse into subdirectories.
        Return:
            map (contract_name => ABI)
        """
        files = []
        for contract in os.listdir(contracts_dir):
            contract_path = os.path.join(contracts_dir, contract)
            if not os.path.isfile(contract_path) or '.sol' not in contract_path:
                continue
            files.append(contract_path)

        try:
            res = compile_files(
                files,
                output_values=('abi', 'bin', 'ast'),
                import_remappings=map_dirs,
                optimize=False
            )
            return fix_contract_key_names(res)
        except FileNotFoundError:
            raise Exception('Could not compile the contract. Check that solc is available.')

    def get_contract_abi(self, contract_name: str) -> Dict:
        """ Returns the ABI for a given contract. """
        return self.abi[contract_name]['abi']

    def get_event_abi(self, contract_name: str, event_name: str) -> Dict:
        """ Returns the ABI for a given event. """
        contract_abi = self.get_contract_abi(contract_name)
        return get_event_from_abi(contract_abi, event_name)


if os.path.isfile(CONTRACTS_DIR):
    CONTRACT_MANAGER = ContractManager(CONTRACTS_DIR)
else:
    CONTRACT_MANAGER = ContractManager(CONTRACTS_SOURCE_DIRS)
