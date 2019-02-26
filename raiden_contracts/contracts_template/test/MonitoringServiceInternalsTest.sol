pragma solidity 0.5.4;

import "services/MonitoringService.sol";

contract MonitoringServiceInternalsTest is MonitoringService {

    constructor(
        address _token_address,
        address _service_registry_address,
        address _udc_address
    )
        MonitoringService(
            _token_address,
            _service_registry_address,
            _udc_address
        )
        public
    {
    }

    function updateRewardPublic(
        address token_network_address,
        address closing_participant,
        address non_closing_participant,
        uint256 reward_amount,
        uint256 nonce,
        address monitoring_service_address,
        bytes memory reward_proof_signature
    )
        public
    {
        MonitoringService.updateReward(
            token_network_address,
            closing_participant,
            non_closing_participant,
            reward_amount,
            nonce,
            monitoring_service_address,
            reward_proof_signature
        );
    }

    function rewardNonce(bytes32 reward_identifier)
        view
        public
        returns (uint256 nonce)
    {
        return rewards[reward_identifier].nonce;
    }
}
