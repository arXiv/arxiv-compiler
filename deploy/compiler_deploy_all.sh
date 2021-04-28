#!/bin/bash

# Deploy all compiler related services
#
# This includes: compiler_api (front end), compiler_worker, storage, 
#      excludes: redis (external service dependency)

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

echo
echo "Displaying existing deployments and services"
kubectl get pods

echo
echo "Install configmap"
./configmap_update.sh

echo
echo "Persistent Volumes"
kubectl apply -f yaml/compiler-persistent-volume-claim.yaml
kubectl apply -f yaml/nfs-persistent-volume-claim.yaml
kubectl apply -f yaml/nfs-server.yaml

echo
echo "Deploy Storage Container (temporary)"
kubectl apply -f yaml/storage-app-svc.yaml

echo "Deploy secrets"
kubectl apply -f yaml/compiler-secrets.yaml

echo
echo "Deploy compiler worker"
kubectl apply -f yaml/compiler-worker.yaml

# Give some time for worker to start
sleep 3

echo
echo "Deploy compiler api and service"
kubectl apply -f yaml/compiler-api-svc.yaml

echo
echo "Displaying updated deployments and services"
sleep 5
kubectl get pods

