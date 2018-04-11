pragma solidity ^0.4.17;

contract SecretRegistry {

    /*
     *  Data structures
     */

    string constant public contract_version = "0.3._";

    // secrethash => block number at which the secret was revealed
    mapping(bytes32 => uint256) public secrethash_to_block;

    /*
     *  Events
     */

    event SecretRevealed(bytes32 indexed secrethash);

    function registerSecret(bytes32 secret) public returns (bool) {
        bytes32 secrethash = keccak256(secret);
        if (secrethash_to_block[secrethash] > 0) {
            return false;
        }
        secrethash_to_block[secrethash] = block.number;
        SecretRevealed(secrethash);
        return true;
    }
}
