Release Process Document
========================

**This document has not been tested.**

Outline of the release process
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. create and verify that contracts.json file matches the current source code
2. deploy contracts with our deployment scripts and verify them on etherscan (we have a script for this that needs improvements)
3. Step 2 also creates the deployment_*.json files automatically & also verifies the correctness of the info against the chain.
4. Commit, make a PR
5. Push the release tag on master directly -> this triggers the package release in travis; at this point everything should be checked and verified already by the CI tests (compiled data from contracts.json) and the checks that we have in place (deployment info, checks are in the deployment scripts)
