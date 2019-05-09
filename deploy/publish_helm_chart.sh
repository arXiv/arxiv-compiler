#!/bin/bash

set -o pipefail
set -o errexit
set -o nounset


export LOGLEVEL=40
if [ -z "${TRAVIS_TAG}" ]; then
    export SOURCE_REF=${TRAVIS_COMMIT}
else
    export SOURCE_REF=${TRAVIS_TAG}
fi

helm package --version ${SOURCE_REF} --app-version ${SOURCE_REF} ./deploy/compiler/
helm s3 push compiler-${SOURCE_REF}.tgz arxiv  || echo "This chart version already published"
