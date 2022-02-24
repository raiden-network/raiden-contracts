#!/usr/bin/env python3
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

import os
from typing import List

from setuptools import Command
from setuptools.command.build_py import build_py

DESCRIPTION = "Raiden contracts library and utilities"
VERSION = "0.40.3"


def read_requirements(path: str) -> List[str]:
    assert os.path.isfile(path)
    with open(path) as requirements:
        return requirements.read().split()


def _get_single_requirement(requirements: List[str], package: str) -> List[str]:
    return [req for req in requirements if req.startswith(package)]


class BuildPyCommand(build_py):
    def run(self) -> None:
        try:
            self.run_command("verify_contracts")
        except SystemExit:
            pass
        build_py.run(self)


class VerifyContracts(Command):
    description = "Verify that the compiled contracts have the correct source code checksum"
    user_options: List = []

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass

    def run(self) -> None:  # pylint: disable=no-self-use
        from raiden_contracts.contract_manager import contracts_precompiled_path
        from raiden_contracts.contract_source_manager import (
            ContractSourceManager,
            contracts_source_path,
        )

        manager = ContractSourceManager(contracts_source_path(contracts_version=None))
        manager.verify_precompiled_checksums(contracts_precompiled_path())


class CompileContracts(Command):
    description = "Compile contracts and add ABI and checksums to a json file"
    user_options: List = []

    def initialize_options(self) -> None:
        pass

    def finalize_options(self) -> None:
        pass

    def run(self) -> None:  # pylint: disable=no-self-use
        from raiden_contracts.contract_manager import contracts_precompiled_path
        from raiden_contracts.contract_source_manager import (
            ContractSourceManager,
            contracts_source_path,
        )

        contract_manager = ContractSourceManager(contracts_source_path(contracts_version=None))
        contract_manager.compile_contracts(contracts_precompiled_path())


requirements = read_requirements("requirements.txt")

config = {
    "version": VERSION,
    "scripts": [],
    "name": "raiden-contracts",
    "author": "Brainbot Labs Est.",
    "author_email": "contact@brainbot.li",
    "description": DESCRIPTION,
    "url": "https://github.com/raiden-network/raiden-contracts/",
    "license": "MIT",
    "keywords": "raiden ethereum blockchain",
    "install_requires": requirements,
    "setup_requires": requirements,
    "packages": find_packages(),
    "include_package_data": True,
    "classifiers": [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    "entry_points": {"console_scripts": ["deploy = raiden_contracts.deploy.__main__:main"]},
    "cmdclass": {
        "compile_contracts": CompileContracts,
        "verify_contracts": VerifyContracts,
        "build_py": BuildPyCommand,
    },
    "zip_safe": False,
    "package_data": {"raiden_contracts": ["py.typed"]},
}

setup(**config)
