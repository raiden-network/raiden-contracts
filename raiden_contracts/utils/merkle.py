from itertools import zip_longest
from typing import Iterable, List, NamedTuple

from eth_utils import keccak

EMPTY_MERKLE_ROOT = b"\x00" * 32

MerkleTree = NamedTuple("MerkleTree", [("layers", List[List[bytes]])])


def _hash_pair(first: bytes, second: bytes) -> bytes:
    """ Computes the hash of the items in lexicographic order """
    if first is None:
        return second

    if second is None:
        return first

    if first > second:
        ret: bytes = keccak(second + first)
    else:
        ret = keccak(first + second)

    return ret


def compute_merkle_tree(items: Iterable[bytes]) -> MerkleTree:
    """ Calculates the merkle root for a given list of items """

    if not all(isinstance(l, bytes) and len(l) == 32 for l in items):
        raise ValueError("Not all items are hashes")

    leaves = sorted(items)
    if len(leaves) == 0:
        return MerkleTree(layers=[[EMPTY_MERKLE_ROOT]])

    if not len(leaves) == len(set(leaves)):
        raise ValueError("The leaves items must not contain duplicate items")

    tree = [leaves]
    layer = leaves
    while len(layer) > 1:
        # [a, b, c, d, e] -> [(a, b), (c, d), (e, None)]
        iterator = iter(layer)
        paired_items = zip_longest(iterator, iterator)

        layer = [_hash_pair(a, b) for a, b in paired_items]
        tree.append(layer)

    return MerkleTree(layers=tree)


def get_merkle_root(merkle_tree: MerkleTree) -> bytes:
    """ Returns the root element of the merkle tree. """
    assert merkle_tree.layers, "the merkle tree layers are empty"
    assert merkle_tree.layers[-1], "the root layer is empty"

    return merkle_tree.layers[-1][0]
