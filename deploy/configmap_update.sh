#!/bin/bash

CONFIG="config.sh"

if [ -f "$CONFIG" ]; then
    source $CONFIG
else
    echo "Config file '$CONFIG' not found"
fi

echo "Map: $CONFIGMAP"

# See what config maps are available
current=$(kubectl get configmap | grep $CONFIGMAP)
if [ "$current" ]; then
  echo "Current configmap:"
  echo "  $current"
else
  echo "Configmap doesn't exist: creating configmap $CONFIGMAP"
fi

#Install updated configmap
#kubectl create configmap compiler-configmap --from-env-file compiler-configmap.env 

config_file_path="config/"$CONFIGMAP".yaml"

echo "Updated Configmap: $CONFIGMAP"
kubectl apply -f $config_file_path

# Show update
echo "Updating configmap:"
updated=$(kubectl get configmap | grep $CONFIGMAP)
echo "  $updated"
echo
echo "Would you like to restart compiler API and worker deployments?"
echo "  You may want to skip restart if you are also deploying"
echo "  changes to these services."
read -r -p "Are You Sure? [Y/n] " response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
  echo "Restarted..."
  kubectl get pods
  kubectl rollout restart deployment.apps/compiler-api 
  kubectl rollout restart deployment.apps/compiler-worker
  sleep 3
  echo "Restarted..."
  kubectl get pods
else
  echo "Skipping deployment update. Current configmap values may not be "
  echo "reflected in current deployments."
fi
