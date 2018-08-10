#!/usr/bin/env python3
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

import os
from setuptools import Command
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

DESCRIPTION = 'Raiden contracts library and utilities'
VERSION = '0.2.0'


def read_requirements(path: str):
    assert os.path.isfile(path)
    with open(path) as requirements:
        return requirements.read().split()


class BuildPyCommand(build_py):
    def run(self):
        try:
            self.run_command('compile_contracts')
        except SystemExit:
            pass
        build_py.run(self)


class SdistCommand(sdist):
    def run(self):
        from raiden_contracts.contract_manager import CONTRACTS_PRECOMPILED_PATH

        if not CONTRACTS_PRECOMPILED_PATH.is_file():
            try:
                self.run_command('build')
            except SystemExit:
                pass
        super().run()


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

        try:
            from solc import compile_files  # noqa
        except ModuleNotFoundError:
            print('py-solc is not installed, skipping contracts compilation')
            return

        from raiden_contracts.contract_manager import (
            ContractManager,
            CONTRACTS_PRECOMPILED_PATH,
            CONTRACTS_SOURCE_DIRS,
        )

        try:
            contract_manager = ContractManager(CONTRACTS_SOURCE_DIRS)
            contract_manager.store_compiled_contracts(CONTRACTS_PRECOMPILED_PATH)
        except RuntimeError:
            import traceback
            print("Couldn't compile the contracts!")
            traceback.print_exc()


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
    'install_requires': read_requirements('requirements.txt'),
    'packages': find_packages(),
    'include_package_data': True,
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ],
    'entry_points': {
        'console_scripts': ['deploy = raiden_contracts.deploy.__main__:main'],
    },
    'cmdclass': {
        'compile_contracts': CompileContracts,
        'build_py': BuildPyCommand,
        'sdist': SdistCommand,
    },
}

setup(**config)
