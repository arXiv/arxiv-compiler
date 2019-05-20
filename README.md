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
$ export CONVERTER_DOCKER_IMAGE=[name (including transport) of converter image]
$ export FILEMANAGER_ENDPOINT=https://arxiv.org  # Get public sources.
$ export FILEMANAGER_CONTENT_PATH=/src/{source_id}
```

And then run with:

```bash
$ docker-compose build    # Build the local images.
$ docker-compose up       # Start the service group.
```

Give it a few seconds; Localstack needs to come up (provides a local S3), and
a bucket will be created.

### Authentication + Authorization

To use the API you will need an auth token with scopes ``compile:read`` and
``compile:create``. The easiest way to generate one of these is to use the
helper script
[here](https://github.com/arXiv/arxiv-auth/blob/develop/generate_token.py).
Make sure that you use the same ``JWT_SECRET`` that is used in
``docker-compose.yml``.


```bash
JWT_SECRET=foosecret pipenv run python generate_token.py
```

You should pass this token as the value of the ``Authorization`` header in
all requests to the API. For example:

```bash
curl -XPOST -H "Authorization: [auth token]" http://127.0.0.1:8000/...
```

For requests in your browser, you can use something like
[requestly](https://chrome.google.com/webstore/detail/requestly-redirect-url-mo/mdnleldcmiljblolnjhpnblkcekpdkpa?hl=en)
to automatically add the auth header to your requests.

### Request compilation

```bash
$ curl -XPOST -i -H 'Authorization: {JWT}' -d '{"source_id":"1602.00123","checksum":"\"Tue, 02 Feb 2016 01:04:33 GMT\"","format":"pdf"}' http://localhost:8000/
HTTP/1.0 202 ACCEPTED
Content-Type: application/json
Content-Length: 3
Location: http://localhost:8000/task/53cccb2e-faf7-4dfa-b8de-63854bd08b0a
Server: Werkzeug/0.14.1 Python/3.6.4
Date: Mon, 12 Nov 2018 10:41:42 GMT

{}
```

You should get ``202 Accepted`` with headers that look like this:

```bash
content-type: application/json
content-length: 3
location: http://127.0.0.1:8000/1901.00123/%22Thu%2C%2003%20Jan%202019%2001:04:33%20GMT%22/pdf
server: Werkzeug/0.15.2 Python/3.6.5
date: Wed, 08 May 2019 20:49:26 GMT
```

The ``location`` is the status resource for the compilation task.

#### What's with the ``checksum`` entry in the request payload?

Note that the compiler service assumes that the checksum of the source package
is included in the ``ETag`` header (this is the behavior of the file manager
service). If you are pulling sources from the core arXiv site (as above), this
will be a datestamp instead of a checksum. You can get the current ETag for a
source package like this:

```bash
$ curl -I https://arxiv.org/src/1901.00123
HTTP/1.1 200 OK
Date: Wed, 08 May 2019 20:29:32 GMT
Server: Apache
ETag: "Thu, 03 Jan 2019 01:04:33 GMT"
Expires: Thu, 09 May 2019 00:00:00 GMT
Content-Encoding: x-gzip
Content-Disposition: attachment; filename="arXiv-1901-00123v1.tar.gz"
Strict-Transport-Security: max-age=31536000
Set-Cookie: browser=128.84.116.178.1557347372434122; path=/; max-age=946080000; domain=.arxiv.org
Last-Modified: Thu, 03 Jan 2019 01:04:33 GMT
Content-Length: 111118
Vary: User-Agent
Content-Type: application/x-eprint-tar
```

**Note that the quotation marks are included as part of the value of the ETag/checksum
field in the request.**

### Checking the compilation status endpoint

You can request the status endpoint like this:

```bash
$ curl -H 'Authorization: {JWT}' http://127.0.0.1:8000/1901.00123/%22Thu%2C%2003%20Jan%202019%2001:04:33%20GMT%22/pdf
{
    "checksum": "\"Thu, 03 Jan 2019 01:04:33 GMT\"",
    "description": "",
    "output_format": "pdf",
    "owner": null,
    "reason": null,
    "size_bytes": 598859,
    "source_id": "1901.00123",
    "status": "completed",
    "task_id": "1901.00123/\"Thu, 03 Jan 2019 01:04:33 GMT\"/pdf"
}
```

### Getting the content

You can get the content at:
http://127.0.0.1:8000/1901.00123/%22Thu%2C%2003%20Jan%202019%2001:04:33%20GMT%22/pdf/content


## Documentation

The latest documentation can be found at
https://arxiv.github.io/arxiv-compiler.

### Building

```bash
sphinx-apidoc -o docs/source/api/ -e -f -M compiler *test*/*
cd docs/
make html SPHINXBUILD=$(pipenv --venv)/bin/sphinx-build
```


## License

See [LICENSE](./LICENSE).
