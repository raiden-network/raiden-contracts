#!/usr/bin/env bash
set -o xtrace

set -e

fail() {
    if [[ $- == *i* ]]; then
       red=`tput setaf 1`
       reset=`tput sgr0`

       echo "${red}==> ${@}${reset}"
    fi
    exit 1
}

info() {
    if [[ $- == *i* ]]; then
        blue=`tput setaf 4`
        reset=`tput sgr0`

        echo "${blue}${@}${reset}"
    fi
}

success() {
    if [[ $- == *i* ]]; then
        green=`tput setaf 2`
        reset=`tput sgr0`
        echo "${green}${@}${reset}"
    fi

}

warn() {
    if [[ $- == *i* ]]; then
        yellow=`tput setaf 3`
        reset=`tput sgr0`

        echo "${yellow}${@}${reset}"
    fi
}

[ -z "${SOLC_URL}" ] && fail 'missing SOLC_URL'
[ -z "${SOLC_VERSION}" ] && fail 'missing SOLC_VERSION'

if [ ! -x $GITHUB_WORKSPACE/bin/solc-${SOLC_VERSION} ]; then
    mkdir -p $GITHUB_WORKSPACE/bin

    curl -L $SOLC_URL > $GITHUB_WORKSPACE/bin/solc-${SOLC_VERSION}
    chmod 775 $GITHUB_WORKSPACE/bin/solc-${SOLC_VERSION}
    echo "$GITHUB_WORKSPACE/bin" >> $GITHUB_PATH

    success "solc ${SOLC_VERSION} installed"
else
    info 'using cached solc'
fi

# always recreate the symlink since we dont know if it's pointing to a different
# version
[ -h $GITHUB_WORKSPACE/bin/solc ] && unlink $GITHUB_WORKSPACE/bin/solc
ln -s $GITHUB_WORKSPACE/bin/solc-${SOLC_VERSION} $GITHUB_WORKSPACE/bin/solc
