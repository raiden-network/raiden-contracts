pragma solidity ^0.4.17;

import "raiden/TokenNetwork.sol";

contract UnlockTest is TokenNetwork {
    function UnlockTest (
        address _token_address,
        address _secret_registry,
        uint256 _chain_id)
        TokenNetwork(
            _token_address,
            _secret_registry,
            _chain_id)
        public
    {

    }

    function getMerkleRootAndUnlockedAmountPublic(
        bytes merkle_tree)
        view
        public
        returns (bytes32, uint256)
    {
        return getMerkleRootAndUnlockedAmount(merkle_tree);
    }
}
