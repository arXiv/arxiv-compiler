#!/bin/bash

# Delete cluster

# Relies on the following environment variables:
#
# CLUSTER

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

CLUSTER_TYPE=zone
CLUSTER_VALUE=$CLUSTER_ZONE

exists=$(gcloud container clusters list --$CLUSTER_TYPE=$CLUSTER_VALUE --filter=$CLUSTER)

if [ "$exists" ]; then
    echo "Delete cluster '$CLUSTER' and all it's resources!"
    read -r -p "Are You Sure? [Y/n] " response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]
    then
        gcloud container clusters delete $CLUSTER --$CLUSTER_TYPE=$CLUSTER_VALUE
        gcloud container clusters list --$CLUSTER_TYPE=$CLUSTER_VALUE --filter=$CLUSTER
    else
        echo "Aborting delete cluster request"
    fi
else
    echo "Cluster $CLUSTER does not exist!"
    gcloud container clusters list 
    exit 1
fi
