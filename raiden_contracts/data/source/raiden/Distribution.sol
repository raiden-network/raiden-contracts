pragma solidity 0.6.10;

import "test/CustomToken.sol";
import "raiden/Utils.sol";
import "lib/ECVerify.sol";

contract Distribution is Utils {
    CustomToken public token;

    // Chain ID as specified by EIP155 used in balance proof signatures to
    // avoid replay attacks
    uint256 public chain_id;

    address claim_creator;

    mapping(address => uint256) public withdraws;

    constructor(
        address _token_address,
        uint256 _chain_id,
        address _claim_creator
    )
        public
    {
        require(_token_address != address(0x0));
        require(_chain_id > 0);
        require(_claim_creator != address(0x0));

        token = CustomToken(_token_address);
        chain_id = _chain_id;
        claim_creator = _claim_creator;
    }

    function claim(
        address owner,
        address partner,
        uint256 total_amount,
        bytes memory signature
    ) public {
        address creator = recoverAddressFromClaim(
            owner,
            partner,
            total_amount,
            signature
        );

        require(creator == claim_creator, "Signature mismatch");

        uint256 already_claimed = withdraws[owner];
        require(total_amount > already_claimed, "Already claimed");

        withdraws[owner] = total_amount;
        uint256 mint_amount = total_amount - already_claimed;

        token.mintFor(mint_amount, owner);
    }

    function recoverAddressFromClaim(
        address owner,
        address partner,
        uint256 amount,
        bytes memory signature
    )
        internal
        view
        returns (address signature_address)
    {
        // Length of the actual message: 32 + 20 + 20 + 20 + 32
        bytes32 message_hash = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n124",
            address(this),
            chain_id,
            owner,
            partner,
            amount
        ));

        return ECVerify.ecverify(message_hash, signature);
    }
}
