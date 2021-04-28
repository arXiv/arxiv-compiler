#!/bin/bash

# Create Redis cluster

set -e

# Relies on the following environment variales:
#	PROJECT
#	REDIS_NAME
#	REDIS_ZONE
#	REDIS_REGION

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

# Make sure api is enabled
gcloud services enable redis.googleapis.com

# Check if Redis is running
exists=$(gcloud redis instances list  --region=$REDIS_REGION --project=$PROJECT)

if [[ $exists =~ $REDIS_NAME ]]; then
    echo "ERROR: Redis '$REDIS_NAME' already exists in region. Use or delete existing Redis."
    echo $exists
else
     gcloud redis instances create $REDIS_NAME --tier=basic --redis-version=redis_4_0 --region=$REDIS_REGION --zone=$REDIS_ZONE --project=$PROJECT
     gcloud redis instances list  --region=$REDIS_REGION --project=$PROJECT
fi
