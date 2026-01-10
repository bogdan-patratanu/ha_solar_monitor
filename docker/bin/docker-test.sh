#!/bin/sh

service_info(){
    service=$1
    echo ""
    echo -e "Testing service '\e[1m$service\e[0m'"
    echo "======="
}

assert_result(){
    if [ "$1" = true ];
    then
        echo -e "\e[32;1mOK\e[0m"
    else
        echo -e "\e[31;1mERROR\e[0m"
    fi;
}

docker_exec(){
    service=$1
    shift;
    docker exec $(docker ps --filter name=${service} -q | head -1) "$@"
}

test_container_is_running(){
    service=$1
    result=false
    echo "Checking if '${service}' has a running container"
    echo "$(docker ps --filter name=${service})" | grep -q "${service}" && result=true
    assert_result ${result}
}

test_host_docker_internal(){
    service=$1
    result=false
    echo "Checking 'host.docker.internal' on '${service}'"
    docker_exec ${service} dig host.docker.internal | grep -vq NXDOMAIN && result=true
    assert_result ${result}
}

service="app"
service_info ${service}
test_container_is_running ${service}
test_host_docker_internal ${service}
