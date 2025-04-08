#!/bin/bash

# Shutdown all compiler related services
#
# This includes: compiler_api (front end), compiler_worker, storage, 
#      excludes: redis (external service dependency)

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

# Don't shut down storage for now - need to detect ip for other configs
echo "Shutting down compiler API and worker deployment."
echo

echo "Displaying existing deployments and services"
kubectl get all

echo "Shutdown compiler worker"
kubectl delete deployment.apps/compiler-worker

echo "Shutdown compiler api and service"
kubectl delete deployment.apps/compiler-api
kubectl delete service/compiler-api

echo "Displaying remaining deployments and services"
kubectl get all

