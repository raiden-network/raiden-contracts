pragma solidity 0.5.4;

import "lib/ECVerify.sol";
import "raiden/Token.sol";
import "raiden/Utils.sol";
import "raiden/TokenNetwork.sol";
import "services/ServiceRegistry.sol";
import "services/UserDeposit.sol";

contract MonitoringService is Utils {
    string constant public contract_version = "0.8.0_unlimited";

    // Token to be used for paying the rewards
    Token public token;

    // Raiden Service Bundle contract to use for checking if MS has deposits
    ServiceRegistry public service_registry;
    UserDeposit public user_deposit;

    // keccak256(channel_identifier, token_network_address) => Struct
    // Keep track of the rewards per channel
    mapping(bytes32 => Reward) rewards;

    /*
     *  Structs
     */
    struct Reward{
        // The amount of tokens to be rewarded
        uint256 reward_amount;

        // Nonce of the most recently provided BP
        uint256 nonce;

        // Address of the Raiden Node that was monitored
        // This is also the address that has the reward deducted from its deposit
        address reward_sender_address;

        // Address of the Monitoring Service who is currently eligible to claim the reward
        address monitoring_service_address;
    }

    /*
     *  Events
     */

    event NewBalanceProofReceived(
        address token_network_address,
        uint256 channel_identifier,
        uint256 reward_amount,
        uint256 indexed nonce,
        address indexed ms_address,
        address indexed raiden_node_address
    );
    event RewardClaimed(address indexed ms_address, uint amount, bytes32 indexed reward_identifier);

    /*
     *  Modifiers
     */

    modifier canMonitor(address _ms_address) {
        require(service_registry.deposits(_ms_address) > 0);
        _;
    }

    /*
     *  Constructor
     */

    /// @notice Set the default values for the smart contract
    /// @param _token_address The address of the token to use for rewards
    /// @param _service_registry_address The address of the ServiceRegistry contract
    constructor(
        address _token_address,
        address _service_registry_address,
        address _udc_address
    )
        public
    {
        require(_token_address != address(0x0));
        require(_service_registry_address != address(0x0));
        require(_udc_address != address(0x0));
        require(contractExists(_token_address));
        require(contractExists(_service_registry_address));
        require(contractExists(_udc_address));

        token = Token(_token_address);
        service_registry = ServiceRegistry(_service_registry_address);
        user_deposit = UserDeposit(_udc_address);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);
        // Check if the contract is indeed a service_registry contract
        // TODO: Check that some function exists in the contract
    }

    /// @notice Internal function that updates the Reward struct if a newer balance proof
    /// is provided in the monitor() function
    /// @param token_network_address Address of the TokenNetwork being monitored
    /// @param closing_participant The address of the participant who closed the channel
    /// @param non_closing_participant Address of the other channel participant. This is
    /// the participant on whose behalf the MS acts.
    /// @param reward_amount The amount of tokens to be rewarded
    /// @param nonce The nonce of the newly provided balance_proof
    /// @param monitoring_service_address The address of the MS calling monitor()
    /// @param reward_proof_signature The signature of the signed reward proof
    function updateReward(
        address token_network_address,
        address closing_participant,
        address non_closing_participant,
        uint256 reward_amount,
        uint256 nonce,
        address monitoring_service_address,
        bytes memory reward_proof_signature
    )
    internal
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);
        uint256 channel_identifier = token_network.getChannelIdentifier(
            closing_participant, non_closing_participant
        );

        // Make sure that the reward proof is signed by the non_closing_participant
        address raiden_node_address = recoverAddressFromRewardProof(
            channel_identifier,
            reward_amount,
            token_network_address,
            token_network.chain_id(),
            nonce,
            reward_proof_signature
        );
        require(raiden_node_address == non_closing_participant);

        bytes32 reward_identifier = keccak256(abi.encodePacked(
            channel_identifier,
            token_network_address
        ));

        // Get the Reward struct for the correct channel
        Reward storage reward = rewards[reward_identifier];

        // Only allow BPs with higher nonce to be submitted
        require(reward.nonce < nonce);

        // MSC stores channel_identifier, MS_address, reward_amount, nonce
        // of the MS that provided the balance_proof with highest nonce
        rewards[reward_identifier] = Reward({
            reward_amount: reward_amount,
            nonce: nonce,
            reward_sender_address: non_closing_participant,
            monitoring_service_address: monitoring_service_address
        });
    }

    /// @notice Called by a registered MS, when providing a new balance proof
    /// to a monitored channel.
    /// Can be called multiple times by different registered MSs as long as the BP provided
    /// is newer than the current newest registered BP.
    /// @param nonce Strictly monotonic value used to order BPs
    /// omitting PB specific params, since these will not be provided in the future
    /// @param reward_amount Amount of tokens to be rewarded
    /// @param token_network_address Address of the Token Network in which the channel
    /// being monitored exists.
    /// @param reward_proof_signature The signature of the signed reward proof
    function monitor(
        address closing_participant,
        address non_closing_participant,
        bytes32 balance_hash,
        uint256 nonce,
        bytes32 additional_hash,
        bytes memory closing_signature,
        bytes memory non_closing_signature,
        uint256 reward_amount,
        address token_network_address,
        bytes memory reward_proof_signature
    )
        canMonitor(msg.sender)
        public
    {
        updateReward(
            token_network_address,
            closing_participant,
            non_closing_participant,
            reward_amount,
            nonce,
            msg.sender,
            reward_proof_signature
        );
        TokenNetwork token_network = TokenNetwork(token_network_address);
        uint256 channel_identifier = token_network.getChannelIdentifier(
            closing_participant, non_closing_participant
        );

        // Call updateTransfer in the corresponding TokenNetwork
        token_network.updateNonClosingBalanceProof(
            channel_identifier,
            closing_participant,
            non_closing_participant,
            balance_hash,
            nonce,
            additional_hash,
            closing_signature,
            non_closing_signature
        );

        emit NewBalanceProofReceived(
            token_network_address,
            channel_identifier,
            reward_amount,
            nonce,
            msg.sender,
            non_closing_participant
        );
    }

    /// @notice Called after a monitored channel is settled in order for MS to claim the reward
    /// Can be called once per settled channel by everyone on behalf of MS
    /// @param token_network_address Address of the Token Network in which the channel exists
    /// @param closing_participant Address of the participant of the channel that called close
    /// @param non_closing_participant The other participant of the channel
    function claimReward(
        uint256 channel_identifier,
        address token_network_address,
        address closing_participant,
        address non_closing_participant
    )
        public
        returns (bool)
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);
        bytes32 reward_identifier = keccak256(abi.encodePacked(
            channel_identifier,
            token_network_address
        ));

        // Only allowed to claim, if channel is settled
        // Channel is settled if it's data has been deleted
        TokenNetwork.ChannelState channel_state;
        (, channel_state) = token_network.getChannelInfo(
            channel_identifier,
            closing_participant,
            non_closing_participant
        );
        require(channel_state == TokenNetwork.ChannelState.Removed);

        Reward storage reward = rewards[reward_identifier];

        // Make sure that the Reward exists
        require(reward.reward_sender_address != address(0x0));

        // Add reward to the monitoring service's balance
        require(user_deposit.transfer(
            reward.reward_sender_address,
            reward.monitoring_service_address,
            reward.reward_amount
        ));

        emit RewardClaimed(
            reward.monitoring_service_address,
            reward.reward_amount,
            reward_identifier
        );

        // delete storage
        delete rewards[reward_identifier];
    }

    function recoverAddressFromRewardProof(
        uint256 channel_identifier,
        uint256 reward_amount,
        address token_network_address,
        uint256 chain_id,
        uint256 nonce,
        bytes memory signature
    )
        pure
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(abi.encodePacked(
            "\x19Ethereum Signed Message:\n148",
            channel_identifier,
            reward_amount,
            token_network_address,
            chain_id,
            nonce
        ));

        signature_address = ECVerify.ecverify(message_hash, signature);
    }
}
