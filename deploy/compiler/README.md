# Deployment Instructions for compiler

To install `compiler` and `compiler-worker` to the development namespace in the
kubernetes cluster:


```bash
helm install ./ --name=compiler --set=image.tag=6b1b6a4 \
  --tiller-namespace=development --namespace=development \
  --set=vault.enabled=1 --set=vault.port=8200 --set=vault.host=<VAULT_HOST> \
  --set=ingress.host=development.arxiv.org \
  --set=redis.host=<REDIS_HOST>
```

This will create *at least* 1 pod for `compiler` and *at least* 1 pod for `compiler-worker`, depending on the how the values for `scaling.worker_replicas` and `scaling.api_replicas` are set; the defaults for both is 3.

The `compiler` pod(s) run a single container called `compiler` and the `compiler-worker` pods run two containers: `compiler-dind-daemon` and `arxiv-compiler-worker`.


To delete the pods associated with `compiler` and `compiler-worker`, run:
```
helm del --purge compiler --tiller-namespace=development
```

Notes:
- `image.tag`: this refers to the tag in [dockerhub](https://hub.docker.com/repository/docker/arxiv/compiler)
- `vault.host`: the actual IP of the Vault host can be retrieved from most of the other pods
- `redis.host`: the Redis cluster is provisioned separately from k8s. See AWS ElastiCache dashboard; get the endpoint from the `tasks-development` cluster (without the port).
