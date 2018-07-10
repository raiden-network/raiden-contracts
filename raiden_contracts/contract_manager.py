import gzip
import hashlib
import json
import logging
import os
import zlib
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, Union

from solc import compile_files
from web3.utils.contracts import find_matching_event_abi


log = logging.getLogger(__name__)

_BASE = Path(__file__).parent

CONTRACTS_PRECOMPILED_PATH = _BASE.joinpath('data', 'contracts.json.gz')
CONTRACTS_SOURCE_DIRS = {
    'raiden': _BASE.joinpath('contracts'),
    'test': _BASE.joinpath('contracts/test'),
}


class ContractManagerError(RuntimeError):
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
        if isinstance(path, dict):
            self._contracts_source_dirs = path
        elif isinstance(path, Path):
            if path.is_dir():
                ContractManager.__init__(self, {'smart_contracts': path})
            else:
                try:
                    with gzip.GzipFile(path, 'rb') as precompiled_file:
                        precompiled_content = json.load(precompiled_file)
                except (JSONDecodeError, UnicodeDecodeError, zlib.error) as ex:
                    raise ContractManagerError(
                        f"Can't load precompiled smart contracts: {ex}",
                    ) from ex
                try:
                    self._contracts = precompiled_content['contracts']
                    self._precompiled_checksum = precompiled_content['checksum']
                except KeyError as ex:
                    raise ContractManagerError(
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
            raise ContractManagerError(
                'Could not compile the contract. Check that solc is available.',
            ) from ex

    def store_compiled_contracts(self, target_path: Path) -> None:
        """ Store compiled contracts JSON at `target_path`. """
        if self._contracts_source_dirs is None:
            raise TypeError("Already using stored contracts.")

        contracts_checksum = self._checksum_contracts()

        # Check if existing file matches checksum
        if target_path.is_file():
            try:
                precompiled_manager = ContractManager(target_path)
                if contracts_checksum == precompiled_manager._precompiled_checksum:
                    # Compiled contracts match source - nothing to be done
                    return
            except ContractManagerError:
                # File was either not json or had a wrong format
                pass

        if not self._contracts:
            self._compile_all_contracts()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.GzipFile(target_path, 'wb') as target_file:
            target_file.write(
                json.dumps(
                    dict(contracts=self._contracts, checksum=contracts_checksum),
                ).encode(),
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
        if not self._contracts:
            self._compile_all_contracts()
        contract_abi = self.get_contract_abi(contract_name)
        return find_matching_event_abi(contract_abi, event_name)

    def _checksum_contracts(self):
        if self._contracts_source_dirs is None:
            raise TypeError("Can't checksum when using precompiled contracts.")
        checksums = []
        for contracts_dir in self._contracts_source_dirs.values():
            file: Path
            for file in contracts_dir.glob('*.sol'):
                checksums.append(
                    '{}:{}'.format(
                        file.name,
                        hashlib.sha256(file.read_bytes()).hexdigest(),
                    ),
                )
        return hashlib.sha256(':'.join(checksums).encode()).hexdigest()


def _fix_contract_key_names(input: Dict) -> Dict:
    result = {}

    for k, v in input.items():
        name = k.split(':')[1]
        result[name] = v

    return result


# The env variable gets set in `setup.py` for the `CompileContracts` step.
if (
    CONTRACTS_PRECOMPILED_PATH.is_file() and
    os.environ.get('_RAIDEN_CONTRACT_MANAGER_SKIP_PRECOMPILED') is None
):
    CONTRACT_MANAGER = ContractManager(CONTRACTS_PRECOMPILED_PATH)
else:
    CONTRACT_MANAGER = ContractManager(CONTRACTS_SOURCE_DIRS)
