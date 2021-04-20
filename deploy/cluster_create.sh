#!/bin/bash

# Create cluster

# Relies on the following environment variables:
#
#	CLUSTER
#	CLUSTER_REGION
#	CLUSTER_NODES

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

exists=$(gcloud container clusters list --filter=$CLUSTER)

if [ $exists ]; then
    echo "ERROR: Cluster '$CLUSTER' already exists!"
    gcloud container clusters list
    echo "Aborting create cluster request. Delete cluster first!"
else
    echo "Creating cluster $CLUSTER now!"
    gcloud container clusters create $CLUSTER --region=$CLUSTER_REGION --enable-ip-alias --num-nodes=$CLUSTER_NODES
    gcloud container clusters list
fi
