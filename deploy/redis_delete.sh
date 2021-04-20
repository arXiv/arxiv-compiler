#!/bin/bash

# Delete Redis cluster

# Relies on the following environment variales:
#       PROJECT
#       REDIS_NAME
#       REDIS_ZONE
#       REDIS_REGION

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

exists=$(gcloud redis instances list  --region=$REDIS_REGION --project=$PROJECT)

if [[ $exists =~ $REDIS_NAME ]]; then
    echo "Delete Redis '$REDIS_NAME' and all it's resources!"
    read -r -p "Are You Sure? [Y/n] " response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]
    then
        gcloud redis instances delete $REDIS_NAME --region=$REDIS_REGION --project=$PROJECT  
        gcloud redis instances list --region=$REDIS_REGION --project=$PROJECT
    else
        echo "Aborting delete cluster request"
    fi
else
    echo "Cluster $REDIS_NAME does not exist!"
    gcloud container clusters list 
    exit 1
fi
