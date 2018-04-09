pragma solidity ^0.4.17;

import "./Token.sol";
import "./Utils.sol";
import "./lib/ECVerify.sol";
import "./SecretRegistry.sol";
import "./TokenNetwork.sol";

contract MonitoringService is Utils {

    Token token; // Only allow RDN?

    // The minimum allowed deposit for a MS
    uint256 minimum_deposit;

    // keep track of registered Monitoring Services
    // A Monitoring Services must deposit to register
    mapping(address => bool) registered_monitoring_services;

    // channel_identifier => Struct
    // Keep track of the rewards per channel
    mapping(uint256 => Reward) rewards;

    // Deposits made by the MSs
    mapping(address => uint) ms_deposits;
    // Deposits made by the raiden nodes
    mapping(address => uint) raiden_node_deposits;

    /*
     *  Structs
     */
    struct Reward{
        // The amount of the reward to be paid out to the MS
        // that provided latest BP
        uint192 reward_amount;

        // Nonce of the most recently provided BP
        uint64 nonce;

        // Address of the monitoring service that provided the most recent BP
        address ms_address;

        // Address of the Raiden Node that was monitored
        // This is also the address that has the reward deducted from its deposit
        address raiden_node_address;

        // Unique ID to prevent replay attacks on other chains
        uint256 chain_id;
    }

    /*
     *  Events
     */

    event MonitoringServiceNewDeposit(address sender, address receiver, uint amount);
    event RaidenNodeNewDeposit(address sender, address receiver, uint amount);
    event RegisteredMonitoringService(address monitoring_service);
    event NewBalanceProofReceived(
        uint192 reward_amount,
        uint64 nonce,
        address ms_address,
        address raiden_node_address
    );
    event RewardClaimed(address ms_address, uint amount, uint256 channel_id);

    /*
     *  Modifiers 
     */

    modifier isMonitor(address _ms_address) {
        require(registered_monitoring_services[_ms_address]);
        _;
    }

    /*
     *  Constructor
     */

    /// @notice Set the default values for the smart contract
    /// @param _token_address The address of the token to use for rewards
    /// @param _minimum_deposit The minimum value that a MS must deposit to be registered
    function MonitoringService(
        address _token_address,
        uint256 _minimum_deposit)
        public
    {
        require(_token_address != 0x0);
        require(_minimum_deposit > 0);
        require(contractExists(_token_address));

        minimum_deposit = _minimum_deposit;

        token = Token(_token_address);
        // Check if the contract is indeed a token contract
        require(token.totalSupply() > 0);
    }

    /// @notice Sets the deposit of a Monitoring Service and registers the MS
    /// Can be called by anyone
    /// @param beneficiary Address of the MS to be registered 
    /// (deposit doesn't have to be paid by the MS address)
    /// @param amount The amount to deposit. Must be higher or equal to minimum_deposit
    function monitorServiceDeposit(address beneficiary, uint amount) {
        require(amount >= minimum_deposit);
        // Do we allow topping up for the MS?
        require(ms_deposits[beneficiary] == 0);

        // Add the deposit for the MS_address
        ms_deposits[beneficiary] =+ amount;

        // Transfer the deposit to the smart contract
        require(token.transferFrom(msg.sender, address(this), amount));

        // Register MS
        registered_monitoring_services[beneficiary] = true;

        emit MonitoringServiceNewDeposit(msg.sender, beneficiary, amount);
    }

    function raidenNodeDeposit(address beneficiary, uint amount) returns (bool) {
        require(amount > 0);

        raiden_node_deposits[beneficiary] =+ amount;

        // Transfer the deposit to the smart contract
        require(token.transferFrom(msg.sender, address(this), amount));

        emit RaidenNodeNewDeposit(msg.sender, beneficiary, amount);
    }

    /// @notice Called by a registered MS, when providing a new balance proof
    /// to a monitored channel.
    /// Can be called multiple times by different registered MSs as long as the PB provided
    /// is newer than the current newest registered BP.
    /// @param channel_identifier Unique identifier for the channel being monitored in a
    /// specific TokenNetwork.
    /// @param nonce Strictly monotonic value used to order PBs
    /// omitting PB specific params, since these will not be provided in the future
    /// @param reward_proof Computed from the reward message. Used for message authentication.
    /// @param reward_amount Amount of tokens to be rewarded to MS if BP
    /// is the last BP to be provided.
    /// @param reward_proof_signature Signature of the Raiden Node signing the reward
    /// @param token_network_address Address of the Token Network in which the channel
    /// being monitored exists.
    function monitor(
        uint256 channel_identifier,
        uint64 nonce,
        uint256 transferred_amount,
        bytes32 locksroot,
        bytes32 additional_hash,
        bytes closing_signature,
        bytes non_closing_signature,
        bytes reward_proof,
        uint192 reward_amount,
        bytes reward_proof_signature,
        address token_network_address)
        isMonitor(msg.sender)
        public
    {
        // Get the Reward struct for the correct channel
        Reward storage reward = rewards[channel_identifier];

        // Only allow PBs with higher nonce to be submitted
        require(reward.nonce < nonce);

        TokenNetwork token_network = TokenNetwork(token_network_address);

        address raiden_node_address = recoverAddressFromRewardProof(
            channel_identifier,
            reward_amount,
            token_network_address,
            token_network.chain_id(),
            nonce,
            reward_proof_signature
        );

        // MSC stores channel_identifier, MS_address, reward_amount, nonce
        // of the MS that provided the balance_proof with highest nonce
        rewards[channel_identifier] = Reward({
            reward_amount: reward_amount,
            nonce: nonce,
            ms_address: msg.sender,
            raiden_node_address: raiden_node_address,
            chain_id: token_network.chain_id()
        });

        // Call updateTransfer in the corresponding TokenNetwork
        token_network.updateTransferDelegate(
            channel_identifier,
            nonce,
            transferred_amount,
            locksroot,
            additional_hash,
            closing_signature,
            non_closing_signature
        );
        emit NewBalanceProofReceived(reward_amount, nonce, msg.sender, raiden_node_address);
    }

    /// @notice Called after a monitored channel is settled in order for MS to claim the reward
    /// Can be called once per settled channel by everyone on behalf of MS
    /// @param channel_identifier Unique identifier for the channel being monitored in a
    /// @param token_network_address Address of the Token Network in which the channel
    function claimReward(
        uint256 channel_identifier,
        address token_network_address)
        //isMonitor(ms_address) // should this function be callable by anyone?
        public
        returns (bool)
    {
        TokenNetwork token_network = TokenNetwork(token_network_address);

        // Only allowed to claim, if channel is settled
        // Channel is settled if it's data has been deleted
        uint256 channel_settle_timeout;
        (channel_settle_timeout, , ) = token_network.getChannelInfo(channel_identifier);
        require(channel_settle_timeout == 0);

        Reward reward = rewards[channel_identifier];

        // Make sure that the Reward exists
        require(reward.ms_address != 0x0);

        // Deduct reward from raiden_node deposit
        raiden_node_deposits[reward.raiden_node_address] =- reward.reward_amount;
        // payout reward
        token.transfer(reward.ms_address, reward.reward_amount);

        emit RewardClaimed(reward.ms_address, reward.reward_amount, channel_identifier);

        // delete storage
        delete rewards[channel_identifier];
    }

    // TODO
    function MonitoringServiceWithdraw() {}

    // TODO
    function raidenNodeWithdraw() {}

    function recoverAddressFromRewardProof(
        uint256 channel_identifier,
        uint192 reward_amount,
        address token_network_address,
        uint256 chain_id,
        uint64 nonce,
        bytes signature
    )
        view
        internal
        returns (address signature_address)
    {
        bytes32 message_hash = keccak256(
            channel_identifier,
            reward_amount,
            token_network_address,
            chain_id,
            nonce
        );

        signature_address = ECVerify.ecverify(message_hash, signature);
    }
}
