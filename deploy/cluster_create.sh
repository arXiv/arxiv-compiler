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

CLUSTER_TYPE=zone
CLUSTER_VALUE=$CLUSTER_ZONE

exists=$(gcloud container clusters list --filter=$CLUSTER)

if [ "$exists" ]; then
    echo "ERROR: Cluster '$CLUSTER' already exists!"
    gcloud container clusters list --$CLUSTER_TYPE=$CLUSTER_VALUE
    echo "Aborting create cluster request. Delete cluster first!"
else
    echo "Creating cluster $CLUSTER now!"
    echo "   Type is $CLUSTER_TYPE and Size is $CLUSTER_NODES"
    gcloud container clusters create $CLUSTER \
      --disk-size "100" \
      --disk-type "pd-standard" \
      --enable-autorepair \
      --enable-autoupgrade \
      --enable-ip-alias \
      --machine-type "e2-medium" \
      --num-nodes=$CLUSTER_NODES \
      --$CLUSTER_TYPE=$CLUSTER_VALUE
      --release-channel "None" \
      --service-account "arxiv-compiler-dev@appspot.gserviceaccount.com"

    gcloud container clusters list
fi
