pragma solidity ^0.4.23;

import "raiden/TokenNetwork.sol";

contract TokenNetworkInternalsTest is TokenNetwork {
    constructor (address _token_address, address _secret_registry, uint256 _chain_id)
        TokenNetwork(_token_address, _secret_registry, _chain_id)
        public
    {

    }

    function getMerkleRootAndUnlockedAmountPublic(bytes merkle_tree)
        view
        public
        returns (bytes32, uint256)
    {
        return getMerkleRootAndUnlockedAmount(merkle_tree);
    }

    function recoverAddressFromWithdrawMessagePublic(
        bytes32 channel_identifier,
        address participant,
        uint256 amount_to_withdraw,
        bytes signature
    )
        view
        public
        returns (address signature_address)
    {
        return recoverAddressFromWithdrawMessage(
            channel_identifier,
            participant,
            amount_to_withdraw,
            signature
        );
    }
}
