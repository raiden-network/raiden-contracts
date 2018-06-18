#!/usr/bin/env python3

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

import os
import json
from setuptools import Command
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

DESCRIPTION = 'Raiden contracts library and utilities'
VERSION = '0.0.1'
COMPILED_CONTRACTS = 'raiden_contracts/data/contracts.json'


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
        if os.path.isfile(COMPILED_CONTRACTS) is False:
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
        try:
            from solc import compile_files  # noqa
        except ModuleNotFoundError:
            print('py-solc is not installed, skipping contracts compilation')
            return
        from raiden_contracts.contract_manager import CONTRACT_MANAGER
        compiled = CONTRACT_MANAGER.precompile_contracts(
            'raiden_contracts/contracts/',
            CONTRACT_MANAGER.get_mappings(),
        )
        with open(COMPILED_CONTRACTS, 'w') as compiled_json:
            compiled_json.write(json.dumps(compiled))


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
        'sdist': SdistCommand
    }
}

setup(**config)
