import hashlib
import json
import logging
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
        self.contracts_source_dirs: Dict[str, Path] = None
        self.contracts = dict()
        self.overall_checksum = None
        self.contracts_checksums = None
        if isinstance(path, dict):
            self.contracts_source_dirs = path
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
                    self.contracts = precompiled_content['contracts']
                    self.overall_checksum = precompiled_content['overall_checksum']
                    self.contracts_checksums = precompiled_content['contracts_checksums']
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
        if self.contracts_source_dirs is None:
            raise TypeError("Missing contracts source path, can't compile contracts.")

        import_dir_map = ['%s=%s' % (k, v) for k, v in self.contracts_source_dirs.items()]
        try:
            for contracts_dir in self.contracts_source_dirs.values():
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
                self.contracts.update(_fix_contract_key_names(res))
        except FileNotFoundError as ex:
            raise ContractManagerCompilationError(
                'Could not compile the contract. Check that solc is available.',
            ) from ex

    def compile_contracts(self, target_path: Path) -> None:
        """ Store compiled contracts JSON at `target_path`. """
        if self.contracts_source_dirs is None:
            raise TypeError("Already using stored contracts.")

        self.checksum_contracts()

        if self.overall_checksum is None:
            raise ContractManagerCompilationError("Checksumming failed.")

        if not self.contracts:
            self._compile_all_contracts()

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open(mode='w') as target_file:
            target_file.write(
                json.dumps(
                    dict(
                        contracts=self.contracts,
                        contracts_checksums=self.contracts_checksums,
                        overall_checksum=self.overall_checksum,
                    ),
                ),
            )

    def get_contract(self, contract_name: str) -> Dict:
        """ Return ABI, BIN of the given contract. """
        if not self.contracts:
            self._compile_all_contracts()
        return self.contracts[contract_name]

    def get_contract_abi(self, contract_name: str) -> Dict:
        """ Returns the ABI for a given contract. """
        if not self.contracts:
            self._compile_all_contracts()
        return self.contracts[contract_name]['abi']

    def get_event_abi(self, contract_name: str, event_name: str) -> Dict:
        """ Returns the ABI for a given event. """
        # Import locally to avoid web3 dependency during installation via `compile_contracts`
        from web3.utils.contracts import find_matching_event_abi

        if not self.contracts:
            self._compile_all_contracts()
        contract_abi = self.get_contract_abi(contract_name)
        return find_matching_event_abi(contract_abi, event_name)

    def checksum_contracts(self) -> None:
        if self.contracts_source_dirs is None:
            raise TypeError("Missing contracts source path, can't checksum contracts.")

        checksums = {}
        for contracts_dir in self.contracts_source_dirs.values():
            file: Path
            for file in contracts_dir.glob('*.sol'):
                checksums[file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        self.overall_checksum = hashlib.sha256(str(checksums).encode()).hexdigest()
        self.contracts_checksums = checksums

    def verify_precompiled_checksums(self, contracts_precompiled: str) -> None:
        """ Compare source code checksums with those from a precompiled file. """

        # We get the precompiled file data
        contracts_precompiled = ContractManager(contracts_precompiled)

        # Compare the overall source code checksum with the one from the precompiled file
        if self.overall_checksum != contracts_precompiled.overall_checksum:
            raise ContractManagerVerificationError(
                f'overall checksum does not match '
                f'{self.overall_checksum} != {contracts_precompiled.overall_checksum}',
            )

        # Compare each contract source code checksum with the one from the precompiled file
        for contract, checksum in self.contracts_checksums.items():
            try:
                precompiled_checksum = contracts_precompiled.contracts_checksums[contract]
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
