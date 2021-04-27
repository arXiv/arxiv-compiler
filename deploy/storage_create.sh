#!/bin/bash

# Create disks for compilation service

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

echo "Start"

exists=$( gcloud services list | grep file.googleapis.com )

echo "Exists:$exists"

# Enable File storage API
if [ ! "$exists" ]; then
    echo "Enabling File Storage API"
    gcloud services enable file.googleapis.com
    gcloud services list | grep file.googleapis.com
else
    echo "File Storage API is already enabled"
fi

# Create new filesystem for compilation service

exists=$( gcloud filestore instances list )

if [ ! "$exists" ]; then
    gcloud filestore instances create compile-data --zone=$ZONE --tier=standard  --file-share=name="compile_data",capacity=1T --network=name="default"
    gcloud filestore instances list
else
    echo "File store exists"
fi

echo "Create GCP Persistent Disk"
exists=$( gcloud compute disks list | grep "nfs-compile-service-disk" )

if [ ! "$exists" ]; then
  echo "Creating new compute disk"
  gcloud compute disks create --size=10GB --zone=$ZONE nfs-compile-service-disk 
else 
  echo "Disk already exists!"
fi

echo "Done"
