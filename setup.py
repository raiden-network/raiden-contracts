#!/usr/bin/env python3
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

import os
from typing import List

from setuptools import Command
from setuptools.command.build_py import build_py


DESCRIPTION = 'Raiden contracts library and utilities'
VERSION = '0.4.0'


def read_requirements(path: str) -> List[str]:
    assert os.path.isfile(path)
    with open(path) as requirements:
        return requirements.read().split()


def _get_single_requirement(requirements: List[str], package: str) -> List[str]:
    return [req for req in requirements if req.startswith(package)]


class BuildPyCommand(build_py):
    def run(self):
        try:
            self.run_command('verify_contracts')
        except SystemExit:
            pass
        build_py.run(self)


class VerifyContracts(Command):
    description = 'compile contracts to json'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from raiden_contracts.contract_manager import (
            ContractManager,
            CONTRACTS_PRECOMPILED_PATH,
            CONTRACTS_SOURCE_DIRS,
        )
        ContractManager.verify_contracts(CONTRACTS_SOURCE_DIRS, CONTRACTS_PRECOMPILED_PATH)


class CompileContracts(Command):
    description = 'compile contracts to json'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        # This is a workaround to stop a possibly existing invalid
        # precompiled `contracts.json` from preventing us from compiling a new one
        os.environ['_RAIDEN_CONTRACT_MANAGER_SKIP_PRECOMPILED'] = '1'

        from raiden_contracts.contract_manager import (
            ContractManager,
            CONTRACTS_PRECOMPILED_PATH,
            CONTRACTS_SOURCE_DIRS,
        )

        contract_manager = ContractManager(CONTRACTS_SOURCE_DIRS)
        contract_manager.compile_contracts(CONTRACTS_PRECOMPILED_PATH)


requirements = read_requirements('requirements.txt')

config = {
    'version': VERSION,
    'scripts': [],
    'name': 'raiden-contracts',
    'author': 'Brainbot Labs Est.',
    'author_email': 'contact@brainbot.li',
    'description': DESCRIPTION,
    'url': 'https://github.com/raiden-network/raiden-contracts/',
    'license': 'MIT',
    'keywords': 'raiden ethereum blockchain',
    'install_requires': requirements,
    'setup_requires': _get_single_requirement(requirements, 'py-solc'),
    'packages': find_packages(),
    'include_package_data': True,
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    'entry_points': {
        'console_scripts': ['deploy = raiden_contracts.deploy.__main__:main'],
    },
    'cmdclass': {
        'compile_contracts': CompileContracts,
        'verify_contracts': VerifyContracts,
        'build_py': BuildPyCommand,
    },
    'zip_safe': False,
}

setup(**config)
