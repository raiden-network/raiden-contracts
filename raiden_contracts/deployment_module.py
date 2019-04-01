from enum import Enum


class DeploymentModule(Enum):
    """ An enum type for specifying the contracts to query in get_contracts_deployment_info() """
    RAIDEN = 'raiden'
    SERVICES = 'services'
    ALL = 'all'
