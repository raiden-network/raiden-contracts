pragma solidity ^0.4.17;

contract SecretRegistry {

    /*
     *  Data structures
     */

    string constant public contract_version = "0.3._";

    // Secret => block number at which the secret was revealed
    mapping(bytes32 => uint256) public secret_to_block;

    /*
     *  Events
     */

    event SecretRevealed(bytes32 secret);

    function registerSecret(bytes32 secret) public returns (bool) {
        if (secret_to_block[secret] > 0) {
            return false;
        }
        secret_to_block[secret] = block.number;
        SecretRevealed(secret);
        return true;
    }
}
