Development scripts for compilation service.

* config/		- Main configuration file.
* yaml/			- Kubernetes yaml files

###Setup/initialization:	Create cluster, redis, disk storage

  These scripts are intended for development purposes. It is likely that the entire
  submision system will be hosted in the same Kubernetes cluster.

  cluster_create.sh	- Create Kubernetes cluster
  cluster_delete.sh	- Delete Kubernetes cluster (destroys everything!)

  redis_create.sh		- Redis
  redis_delete.sh

  storage_create.sh	- Create some persistent disks for compiler service 
                          to use. This creates the disks. The actual claims are 
                          made elsewhere in the yaml files.

###Configuration:

  The main configuration file for development compilation service is config/compiler-configmap.yaml

  configmap_update.sh - update configmap in GC Kubernetes

###Ongoing Development/Maintenance: (mainly compiler API and worker)

  compiler_deploy_all.sh - Deploy the compiler API, worker containers, 
			   storage (localstack is placeholder).

  worker_deploy_or_update.sh - Update the worker container. Faster when you are
                            developing the worker code.

  compiler_shutdown_all.sh - Shutdown compiler API and worker (currently leaves
			    cluster and redis because these take time to
			    start up and require changing ips in config files)

###Other:

  AWS			- Original AWS Kubernetes configuration files (historical)

