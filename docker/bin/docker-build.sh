#!/bin/sh

CURDIR="$( cd -P "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

dos2unix $CURDIR/../.env;

source $CURDIR/../.env;

docker network inspect backend > /dev/null 2>&1 || \
    docker network create -d ${NETWORKS_DRIVER} backend
