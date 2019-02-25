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
VERSION = '0.11.0'


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
    description = 'Verify that the compiled contracts have the correct source code checksum'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from raiden_contracts.contract_manager import (
            ContractManager,
            contracts_precompiled_path,
            contracts_source_path,
            Flavor,
        )
        manager = ContractManager(contracts_source_path(Flavor.Limited))
        manager.checksum_contracts()
        manager.verify_precompiled_checksums(contracts_precompiled_path(Flavor.Limited))


def render_templates_dir(src, dst):
    assert src.exists(), "cannot use a nonexistent source directory"
    assert src.is_dir(), "render_templates_dir called with a non-directory"
    dst.mkdir(parents=True, exist_ok=True)
    for src_item in src.iterdir():
        render_templates(src_item, dst / src_item.name)


def render_templates_leaf(src, dst):
    assert src.exists(), "cannot use a nonexistent source"
    assert not src.is_dir(), "render_template_leaf called with a directory"
    with src.open(mode='r') as src_file:
        content = src_file.read()
    with dst.open(mode='w') as dst_file:
        dst_file.write(content)


def render_templates(src, dst):  # TODO: there has to be a template thing
    assert src.exists(), "cannot use a nonexistent template"
    if src.is_dir():
        render_templates_dir(src, dst)
    else:
        render_templates_leaf(src, dst)


class RenderTemplates(Command):
    description = 'use pystache to produce contracts_template contracts'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from raiden_contracts.contract_manager import (
            contracts_source_root,
            contracts_template_root,
            Flavor,
        )
        render_templates(contracts_template_root(), contracts_source_root(Flavor.Unlimited))


class CompileContracts(Command):
    description = 'Compile contracts and add ABI and checksums to a json file'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from raiden_contracts.contract_manager import (
            ContractManager,
            contracts_precompiled_path,
            contracts_source_path,
            Flavor,
        )

        contract_manager = ContractManager(contracts_source_path(Flavor.Limited))
        contract_manager.compile_contracts(
            contracts_precompiled_path(Flavor.Limited),
        )


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
        'render_templates': RenderTemplates,
        'verify_contracts': VerifyContracts,
        'build_py': BuildPyCommand,
    },
    'zip_safe': False,
}

setup(**config)
