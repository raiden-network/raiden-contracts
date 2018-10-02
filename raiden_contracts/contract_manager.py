import hashlib
import json
import logging
import os
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, Union

from solc import compile_files


log = logging.getLogger(__name__)

_BASE = Path(__file__).parent

CONTRACTS_PRECOMPILED_PATH = _BASE.joinpath('data', 'contracts.json')
CONTRACTS_SOURCE_DIRS = {
    'raiden': _BASE.joinpath('contracts'),
    'test': _BASE.joinpath('contracts/test'),
}


class ContractManagerCompilationError(RuntimeError):
    pass


class ContractManagerLoadError(RuntimeError):
    pass


class ContractManagerVerificationError(RuntimeError):
    pass


class ContractManager:
    def __init__(self, path: Union[Path, Dict[str, Path]]) -> None:
        """Params:
            path: either path to a precompiled contract JSON file, or a list of
                directories which contain solidity files to compile
        """
        self._contracts_source_dirs: Dict[str, Path] = None
        self._contracts = dict()
        self._precompiled_checksum = None
        self._contracts_checksum = None
        if isinstance(path, dict):
            self._contracts_source_dirs = path
        elif isinstance(path, Path):
            if path.is_dir():
                ContractManager.__init__(self, {'smart_contracts': path})
            else:
                try:
                    with path.open() as precompiled_file:
                        precompiled_content = json.load(precompiled_file)
                except (JSONDecodeError, UnicodeDecodeError) as ex:
                    raise ContractManagerLoadError(
                        f"Can't load precompiled smart contracts: {ex}",
                    ) from ex
                try:
                    self._contracts = precompiled_content['contracts']
                    self._precompiled_checksum = precompiled_content['precompiled_checksum']
                    self._contracts_checksum = precompiled_content['contracts_checksum']
                except KeyError as ex:
                    raise ContractManagerLoadError(
                        f'Precompiled contracts json has unexpected format: {ex}',
                    ) from ex
        else:
            raise TypeError('`path` must be either `Path` or `dict`')

    def _compile_all_contracts(self) -> None:
        """
        Compile solidity contracts into ABI and BIN. This requires solc somewhere in the $PATH
        and also the :ref:`ethereum.tools` python library.
        """
        if self._contracts_source_dirs is None:
            raise TypeError("Missing contracts source path, can't compile contracts.")

        import_dir_map = ['%s=%s' % (k, v) for k, v in self._contracts_source_dirs.items()]
        try:
            for contracts_dir in self._contracts_source_dirs.values():
                res = compile_files(
                    [str(file) for file in contracts_dir.glob('*.sol')],
                    output_values=('abi', 'bin', 'ast'),
                    import_remappings=import_dir_map,
                    optimize=False,
                )
                # Strip `ast` part from result
                # TODO: Remove after https://github.com/ethereum/py-solc/issues/56 is fixed
                res = {
                    contract_name: {
                        content_key: content_value
                        for content_key, content_value in contract_content.items()
                        if content_key != 'ast'
                    } for contract_name, contract_content in res.items()
                }
                self._contracts.update(_fix_contract_key_names(res))
        except FileNotFoundError as ex:
            raise ContractManagerCompilationError(
                'Could not compile the contract. Check that solc is available.',
            ) from ex

    def compile_contracts(self, target_path: Path) -> None:
        """ Store compiled contracts JSON at `target_path`. """
        if self._contracts_source_dirs is None:
            raise TypeError("Already using stored contracts.")

        contracts_checksum = self.checksum_contracts(self._contracts_source_dirs)
        precompiled_checksum = hashlib.sha256(str(contracts_checksum).encode()).hexdigest()

        if not self._contracts:
            self._compile_all_contracts()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open(mode='w') as target_file:
            target_file.write(
                json.dumps(
                    dict(
                        contracts=self._contracts,
                        contracts_checksum=contracts_checksum,
                        precompiled_checksum=precompiled_checksum,
                    ),
                ),
            )

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
        # Import locally to avoid web3 dependency during installation via `compile_contracts`
        from web3.utils.contracts import find_matching_event_abi

        if not self._contracts:
            self._compile_all_contracts()
        contract_abi = self.get_contract_abi(contract_name)
        return find_matching_event_abi(contract_abi, event_name)

    @staticmethod
    def checksum_contracts(contracts_source_dirs: list):
        checksums = {}
        for contracts_dir in contracts_source_dirs.values():
            file: Path
            for file in contracts_dir.glob('*.sol'):
                checksums[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        return checksums

    @staticmethod
    def verify_contracts(contracts_source_dirs: list, contracts_precompiled: str):
        checksummed_sources = ContractManager.checksum_contracts(contracts_source_dirs)
        contracts_precompiled = ContractManager(contracts_precompiled)._contracts_checksum
        for contract, checksum in checksummed_sources.items():
            try:
                precompiled_checksum = contracts_precompiled[contract]
            except KeyError:
                raise ContractManagerVerificationError(
                    f'No checksum for {contract}',
                )
            if precompiled_checksum != checksum:
                raise ContractManagerVerificationError(
                    f'checksum of {contract} does not match {precompiled_checksum} != {checksum}',
                )


def _fix_contract_key_names(input: Dict) -> Dict:
    result = {}

    for k, v in input.items():
        name = k.split(':')[1]
        result[name] = v

    return result


# The env variable gets set in `setup.py` for the `CompileContracts` step.
if (
    CONTRACTS_PRECOMPILED_PATH.is_file() and
    'pytest' not in sys.modules and
    os.environ.get('_RAIDEN_CONTRACT_MANAGER_SKIP_PRECOMPILED') is None
):
    CONTRACT_MANAGER = ContractManager(CONTRACTS_PRECOMPILED_PATH)
else:
    CONTRACT_MANAGER = ContractManager(CONTRACTS_SOURCE_DIRS)
