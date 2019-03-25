#!/usr/bin/env python
import json
import os
import re
import sys
from typing import List, Set

import click
from click.types import File

IMPORT_RE = re.compile(r'^import +["\'](?P<contract>[^"\']+.sol)["\'];$')

"""
Utility to join solidity contracts into a single output file by recursively
resolving imports.

example usage:

$ cd raiden-contracts/raiden_contracts
$ python ./utils/join-contracts.py ./contracts/TokenNetwork.sol joined.sol

"""


class ContractJoiner:
    def __init__(self, import_map=None):
        self.have_pragma = False
        self.seen: Set[str] = set()
        self.import_map = import_map if import_map else {}

    def join(self, contract_file):
        out: List[str] = []
        if contract_file.name in self.seen:
            print('Skipping duplicate {}'.format(contract_file.name), file=sys.stderr)
            return []

        self.seen.add(contract_file.name)
        print('Reading {}'.format(contract_file.name), file=sys.stderr)

        for line in contract_file:
            line = line.strip('\r\n')
            stripped_line = line.strip()
            if stripped_line.startswith('pragma'):
                self._on_pragma_line(
                    line=line,
                    out=out,
                )
            elif stripped_line.startswith('import'):
                self._on_import_line(
                    stripped_line=stripped_line,
                    out=out,
                )
            else:
                out.append(line)
        return out

    def _on_pragma_line(
            self,
            line: str,
            out: List[str],
    ):
        if not self.have_pragma:
            self.have_pragma = True
            out.append(line)

    def _on_import_line(
            self,
            stripped_line: str,
            out: List[str],
    ):
        match = IMPORT_RE.match(stripped_line)
        if match:
            next_file = match.groupdict().get('contract')
            assert next_file
            for prefix, path in self.import_map.items():
                if next_file.startswith(prefix):
                    next_file = next_file.replace(prefix, path)
            if next_file and os.path.exists(next_file):
                with open(next_file) as next_contract:
                    out.extend(self.join(next_contract))


@click.command()
@click.option(
    '--import-map',
    default='{}',
    help='JSON mapping {"path-prefix": "/file/system/path"}',
)
@click.argument('contract', type=File())
@click.argument('output', type=File('w'))
def main(contract, output, import_map):
    import_map = json.loads(import_map)
    output.write('\n'.join(ContractJoiner(import_map).join(contract)))


if __name__ == '__main__':
    main()  # pylint: disable=E1120
