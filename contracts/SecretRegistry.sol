pragma solidity ^0.4.17;

contract SecretRegistry {

    /*
     *  Data structures
     */

    string constant public contract_version = "0.3._";

    // Secret => block number at which the secret was revealed
    // uint64 is sufficient to represent 8774136260326 years with blocks of 15s.
    mapping(bytes32 => uint64) public secret_to_block;

    /*
     *  Events
     */

    event SecretRevealed(bytes32 secret);

    function registerSecret(bytes32 secret) public returns (bool) {
        if (secret_to_block[secret] > 0) {
            return false;
        }
        secret_to_block[secret] = uint64(block.number);
        SecretRevealed(secret);
        return true;
    }
}
