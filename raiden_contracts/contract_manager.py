import json
import logging
from pathlib import Path
from typing import Dict, Union

from solc import compile_files
from web3.utils.contracts import find_matching_event_abi


log = logging.getLogger(__name__)

_BASE = Path(__file__).parent

CONTRACTS_PRECOMPILED_PATH = _BASE.joinpath('data', 'contracts.json')
CONTRACTS_SOURCE_DIRS = {
    'raiden': _BASE.joinpath('contracts'),
    'test': _BASE.joinpath('contracts/test'),
}


class ContractManager:
    def __init__(self, path: Union[Path, Dict[str, Path]]) -> None:
        """Params:
            path: either path to a precompiled contract JSON file, or a list of
                directories which contain solidity files to compile
        """
        self._contracts_source_dirs = None
        self._contracts = dict()
        if isinstance(path, dict):
            self._contracts_source_dirs = path
        elif isinstance(path, Path):
            if path.is_dir():
                ContractManager.__init__(self, {'smart_contracts': path})
            else:
                self._contracts = json.loads(path.read_text())
        else:
            raise TypeError('`path` must be either `Path` or `dict`')

    def _compile_all_contracts(self) -> None:
        """
        Compile solidity contracts into ABI and BIN. This requires solc somewhere in the $PATH
        and also the :ref:`ethereum.tools` python library.
        """
        if self._contracts_source_dirs is None:
            raise TypeError("Can't compile contracts when using precompiled archive.")

        import_dir_map = ['%s=%s' % (k, v) for k, v in self._contracts_source_dirs.items()]
        try:
            for contracts_dir in self._contracts_source_dirs.values():
                res = compile_files(
                    [str(file) for file in contracts_dir.glob('*.sol')],
                    output_values=('abi', 'bin', 'ast'),
                    import_remappings=import_dir_map,
                    optimize=False,
                )
                self._contracts.update(_fix_contract_key_names(res))
        except FileNotFoundError as ex:
            raise RuntimeError(
                'Could not compile the contract. Check that solc is available.',
            ) from ex

    def store_compiled_contracts(self, target_path: Path) -> None:
        """ Store compiled contracts JSON at `target_path`. """
        if self._contracts_source_dirs is None:
            raise TypeError("Already using stored contracts.")

        if not self._contracts:
            self._compile_all_contracts()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(self._contracts))

    def get_contract(self, contract_name: str) -> Dict:
        """ Return ABI, BIN of the given contract. """
        if not self._contracts:
            self._compile_all_contracts()
        return self._contracts[contract_name]

    def get_contract_abi(self, contract_name: str) -> Dict:
        """ Returns the ABI for a given contract. """
        if not self._contracts:
            self._compile_all_contracts()
        return self._contracts[contract_name]['abi']

    def get_event_abi(self, contract_name: str, event_name: str) -> Dict:
        """ Returns the ABI for a given event. """
        if not self._contracts:
            self._compile_all_contracts()
        contract_abi = self.get_contract_abi(contract_name)
        return find_matching_event_abi(contract_abi, event_name)


def _fix_contract_key_names(input: Dict) -> Dict:
    result = {}

    for k, v in input.items():
        name = k.split(':')[1]
        result[name] = v

    return result


if CONTRACTS_PRECOMPILED_PATH.is_file():
    CONTRACT_MANAGER = ContractManager(CONTRACTS_PRECOMPILED_PATH)
else:
    CONTRACT_MANAGER = ContractManager(CONTRACTS_SOURCE_DIRS)
