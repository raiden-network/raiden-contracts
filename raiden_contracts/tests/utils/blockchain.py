from web3 import Web3


def mine_blocks(web3: Web3, num_blocks: int) -> None:
    web3.testing.mine(num_blocks)  # type: ignore
