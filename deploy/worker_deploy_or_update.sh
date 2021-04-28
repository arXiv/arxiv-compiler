#!/bin/bash

# Deploy all compiler releated services
#
# This includes: compiler_api (front end), compiler_worker, storage, 
#      excludes: redis (external service dependency)

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

echo "Displaying existing deployments and services"
kubectl get pods

echo "Deploy compiler worker"
kubectl apply -f yaml/compiler-worker.yaml

echo "Displaying updated deployments and services"
kubectl get pods
