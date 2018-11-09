"""

Parameters supported by autotex "converter" image.

```
 -C cache directory [defaults to paper/format specific directory in PS_CACHE]
 -D pass through for -D dvips flag
 -f output format, only sensible use is -f fInm for pdf generation
 -u add a psmapfile to dvips command "-u +psmapfile"
 -h print usage
 -k do not delete temporary directory
 -P pass through for -P dvips flag
 -p id of paper to process (pre 2007 archive/papernum or new numerical id yymm.\\d{4,5}) (required!)
 -d id to use for decrytion (overrides default to -p id)
 -s do not add stamp to PostScript
 -t pass through for -t dvips flag (letter, legal, ledger, a4, a3, landscape)
 -v verbose logging, that is, print log messages to STDOUT
 (they are always logged to auto_gen_ps.log)
 -q quiet - don't send emails to tex_admin (not the inverse of verbose!)
 -W working directory [defaults to paper/version specific dir in PS_GEN_TMP]
 -X cache DVI file (default: no)
 -Y don't copy PostScript or PDF to cache
 -Z don't gzip PostScript before moving to cache
 -T override the default AUTOTEX_TIMEOUT setting with user value
```

We're going to use:

- -f output format, only sensible use is -f fInm for pdf generation (fInm, dvi, ps)
- -p id of paper to process (pre 2007 archive/papernum or new numerical id yymm.\\d{4,5}) (required!)
- -s do not add stamp to PostScript
- -T override the default AUTOTEX_TIMEOUT setting with user value

- -u add a psmapfile to dvips command "-u +psmapfile"
- -P pass through for -P dvips flag
- -t pass through for -t dvips flag (letter, legal, ledger, a4, a3, landscape)
- -D pass through for -D dvips flag

- -d id to use for decrytion (overrides default to -p id)

Always do this:
- -q quiet - don't send emails to tex_admin (not the inverse of verbose!)
- -Y don't copy PostScript or PDF to cache

"""

import os
from typing import List
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from typing import Optional, Tuple

from flask import current_app

from celery.result import AsyncResult
from celery.signals import after_task_publish

from arxiv.base import logging

from .celery import celery_app
from .domain import CompilationProduct, CompilationStatus
from .services import filemanager, store

logger = logging.getLogger(__name__)


class NoSuchTask(RuntimeError):
    """A request was made for a non-existant task."""


class TaskCreationFailed(RuntimeError):
    """An extraction task could not be created."""


def create_compilation_task(source_id: str, source_checksum: str,
                            output_format: CompilationStatus.Formats,
                            preferred_compiler: Optional[str] = None) -> str:
    """
    Create a new compilation task.

    Parameters
    ----------
    source_id : str
    source_checksum : str
    output_format : str
    preferred_compiler : str

    Returns
    -------
    str
        The identifier for the created compilation task.
    """
    try:
        result = foo_compile.delay(source_id, source_checksum,
                                   output_format.value,
                                   preferred_compiler=preferred_compiler)
        logger.info('compile: started processing as %s' % result.task_id)
    except Exception as e:
        logger.error('Failed to create task: %s', e)
        raise TaskCreationFailed('Failed to create task: %s', e) from e
    return result.task_id


def get_compilation_task(task_id: str) -> CompilationStatus:
    """
    Get the status of an extraction task.

    Parameters
    ----------
    task_id : str
        The identifier for the created extraction task.

    Returns
    -------
    :class:`ExtractionTask`

    """
    result = foo_compile.AsyncResult(task_id)
    data = {}
    if result.status == 'PENDING':
        raise NoSuchTask('No such task')
    elif result.status in ['SENT', 'STARTED', 'RETRY']:
        data['status'] = CompilationStatus.Statuses.IN_PROGRESS
    elif result.status == 'FAILURE':
        data['status'] = CompilationStatus.Statuses.FAILED
        data['result']: str = result.result
    elif result.status == 'SUCCESS':
        data['status'] = CompilationStatus.Statuses.COMPLETED
        _result: Dist[str, str] = result.result
        data['source_id'] = _result['source_id']
        data['format'] = CompilationStatus.Formats(_result['output_format'])
        data['source_checksum'] = _result['source_checksum']
    return CompilationStatus(task_id=task_id, **data)


@celery_app.task
def foo_compile(source_id: str, source_checksum: str,
                output_format: str = 'pdf',
                preferred_compiler: Optional[str] = None) -> dict:
    """Dummy task for testing purposes."""
    logger.debug('executed compile task with %s, %s, %s, %s',
                 source_id, source_checksum, output_format, preferred_compiler)
    return {
        'source_id': source_id,
        'source_checksum': source_checksum,
        'output_format': output_format,
        'preferred_compiler': preferred_compiler
    }


@celery_app.task
def compile(source_id: str, source_checksum: str, output_format: str = 'pdf',
            preferred_compiler: Optional[str] = None) -> dict:
    """
    Retrieves an upload, submits to the converter service, uploads results.

    More or less, the ``main()`` function for compiler. It operates in a
    three-step process:
    1.  Retrieve the source package for ``source_id`` from the file management
        service.
    2.  Use the ``preferred_compiler`` to generate ``format``.
    3.  Upload the results.

    Parameters
    ------------
    source_id: str
        Required. The upload to retrieve.
    source_checksum : str
        The checksum for the source package. This is used to differentiate
        compilation tasks.
    output_format: str
        The desired output format. Default: "pdf". Other potential values:
        "dvi", "html", "ps"
    preferred_compiler: str
        The preferred tex compiler for use with the source package.

    """
    try:
        source = filemanager.get_source_content(source_id)
    except filemanager.NotFound as e:
        raise RuntimeError('Source does not exist') from e

    if source.etag != source_checksum:
        raise RuntimeError('Source etag does not match requested checksum')

    # 2. Generate the compiled files
    # 3. Upload the results to output_endpoint
    with TemporaryDirectory(prefix='arxiv') as source_dir, \
            TemporaryDirectory(prefix='arxiv') as output_dir:
        with tarfile.open(fileobj=source.stream, mode='r:gz') as tar:
            tar.extractall(path=source_dir)

        # 2. Generate the compiled files
        product_path, log_path = compile_source(source_dir, output_dir,
                                                format=format)

        status = CompilationStatus(
            source_id=source_id,
            format=CompilationStatus.Formats(format),
            source_checksum=source_checksum,
            status=CompilationStatus.Statuses.COMPLETED
        )

        # Store the result.
        try:
            with open(product_path, 'rb') as f:
                store.store(CompilationProduct(stream=f, status=status))
            with open(log_path, 'rb') as f:
                store.store_log(CompilationProduct(stream=f, status=status))
            store.set_status(status)
        except Exception as e:  # TODO: look at exceptions in object store.
            raise RuntimeError('Failed to store result') from e
        return status.to_dict()


# TODO: rename []_dvips_flag parameters when we figure out what they mean.
def compile_source(source_dir: str, output_dir: str, paper_id: str,
                   output_format: str = 'pdf', add_stamp: bool = True,
                   timeout: int = 600, add_psmapfile: bool = False,
                   P_dvips_flag: bool = False, dvips_layout: str = 'letter',
                   D_dvips_flag: bool = False,
                   id_for_decryption: Optional[str] = None) -> Tuple[str, str]:
    """Compile a TeX source package."""
    image = current_app.config['COMPILER_DOCKER_IMAGE']

    args = [
        f'-p {paper_id}',
        f'-f {output_format}',
        f'-T {timeout}',
        f'-t {dvips_layout}',
        '-q',
        '-Y'
    ]
    if not add_stamp:
        args.append('-s')
    if add_psmapfile:
        args.append('-u')
    if P_dvips_flag:
        args.append('-P')
    if D_dvips_flag:
        args.append('-D')
    if id_for_decryption is not None:
        args.append(f'-d {id_for_decryption}')

    run_docker(image, args=args,
               volumes=[(source_dir, '/src'), (output_dir, '/out')])

    return (
        os.path.join(output_dir, 'test.pdf'),
        os.path.join(output_dir, 'test.log')
    )


def run_docker(image: str, volumes: list = [], ports: list = [],
               args: List[str] = [], daemon: bool = False) -> None:
    """
    Run a generic docker image.

    In our uses, we wish to set the userid to that of running process (getuid)
    by default. Additionally, we do not expose any ports for running services
    making this a rather simple function.

    Parameters
    ----------
    image : str
        Name of the docker image in the format 'repository/name:tag'
    volumes : list of tuple of str
        List of volumes to mount in the format [host_dir, container_dir].
    args : str
        Arguments to the image's run cmd (set by Dockerfile CMD)
    daemon : boolean
        If True, launches the task to be run forever
    """
    # we are only running strings formatted by us, so let's build the command
    # then split it so that it can be run by subprocess
    opt_user = '-u {}'.format(os.getuid())
    opt_volumes = ' '.join(['-v {}:{}'.format(hd, cd) for hd, cd in volumes])
    opt_ports = ' '.join(['-p {}:{}'.format(hp, cp) for hp, cp in ports])
    cmd = 'docker run --rm {} {} {} {} {}'.format(
        opt_user, opt_ports, opt_volumes, image, ' '.join(args)
    )
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=True)

    if result.returncode:
        logger.error(f"Docker image call '{cmd}' exited {result.returncode}")
        logger.error(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        try:
            result.check_returncode()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f'Compilation failed with {result.returncode}')
