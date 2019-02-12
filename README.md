# arXiv compiler service

The build service compiles LaTeX source packages into PDF, PostScript,
and other formats. This service encompasses the arXiv TeX tree. Compilation
logs are also made available, for example to provide submitters feedback about
compilation failures or warnings.

There are three moving parts:
- The compiler service API, a Flask web app that handles new requests for  
  compilation and makes the results available (or not).
- The compiler worker, a Celery app that grabs sources, dispatches compilation,
  and stores the results.
- The converter Docker image, which does the actual work of compilation and is
  executed by the compiler worker. This contains the arXiv TeX tree.

In addition, the following infrastructure parts are required:
- Redis, used as a task queue between the API and the worker.
- S3, used to store the result of compilation tasks.

## TODO

- [ ] Update the ``schema/``, and implement resource URLs in the response data.

## Running the compiler service locally

The easiest way to get up and running is to launch the whole service group
using Docker Compose. You will need to pull the converter image ahead of time.

If you do not have an instance of the file manager service running, you can
try compiling published sources on the public arXiv.org site.

You will also need a directory that the worker can use as /tmp space.

For example:

```bash
$ mkdir /tmp/compilestuff     # Docker needs access to this.
$ export HOST_SOURCE_ROOT=/tmp/compilestuff
$ export COMPILER_DOCKER_IMAGE=[name (including transport) of converter image]
$ export FILE_MANAGER_ENDPOINT=https://arxiv.org  # Get public sources.
$ export FILE_MANAGER_CONTENT_PATH=/src/{source_id}
```

And then run with:

```bash
$ docker-compose build    # Build the local images.
$ docker-compose up       # Start the service group.
```

Give it a few seconds; Localstack needs to come up (provides a local S3), and
a bucket will be created. Then you should be able to do:

```bash
$ curl -XPOST -i -d '{"source_id":"1602.00123","checksum":"\"Tue, 02 Feb 2016 01:04:33 GMT\"","format":"pdf"}' http://localhost:8000/
HTTP/1.0 202 ACCEPTED
Content-Type: application/json
Content-Length: 3
Location: http://localhost:8000/task/53cccb2e-faf7-4dfa-b8de-63854bd08b0a
Server: Werkzeug/0.14.1 Python/3.6.4
Date: Mon, 12 Nov 2018 10:41:42 GMT

{}
```
