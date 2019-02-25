#!/usr/bin/env python

import click
from pathlib import Path
import subprocess
import re

from raiden_contracts.constants import CONTRACTS_VERSION, CONTRACTS_VERSION_LIMITED

"""
A utility to copy a directory containing Solidity files and
remove code between /*LIMITED-VERSION-START*/ and /*LIMITED-VERSION-STOP*/.

example usage:
$ cd raiden-contracts/raiden_contracts
$ python ./utils/remove_limits.py ./contracts ./contracts-without-limits
"""


def work_on_files(src, dst):
    assert src.exists(), 'src has to exist'
    assert not src.is_dir(), 'src must not be a directory'
    original = subprocess.run(['cat', str(src)], stdout=subprocess.PIPE)
    pattern = r'/\*LIMITED-VERSION-START.*?LIMITED-VERSION-END\*/'
    replaced = re.sub(pattern, '', original.stdout.decode('UTF-8'), flags=re.MULTILINE | re.DOTALL)
    replaced = replaced.replace(CONTRACTS_VERSION, CONTRACTS_VERSION_LIMITED)
    with dst.open(mode='w') as dst_file:
        dst_file.write(replaced)


def work_on_paths(src, dst):
    assert src.exists(), 'src has to exist'
    if src.is_dir():
        work_on_dirs(src, dst)
    else:
        work_on_files(src, dst)


def work_on_dirs(src, dst):
    assert src.exists(), 'src has to be a directory'
    assert src.is_dir(), 'src has to be a directory'
    if not dst.exists():
        dst.mkdir(parents=True)
    assert dst.is_dir(), 'dst has to be a directory'
    for src_child in src.iterdir():
        parts = src_child.parts
        assert len(parts) > 0
        name = parts[-1]
        work_on_paths(src / name, dst / name)


@click.command()
@click.argument('src', type=click.Path(exists=True))
@click.argument('dst', type=click.Path())
def main(src, dst):
    src = Path(src)
    dst = Path(dst)
    work_on_dirs(src, dst)


if __name__ == '__main__':
    main()
