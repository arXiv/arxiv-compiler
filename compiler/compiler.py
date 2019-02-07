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
from typing import List, Dict
import subprocess
import tarfile
import shutil
import tempfile
from tempfile import TemporaryDirectory
from typing import Optional, Tuple

from flask import current_app

from celery.result import AsyncResult
from celery.signals import after_task_publish

from arxiv.base import logging

from .celery import celery_app
from .domain import CompilationProduct, CompilationStatus, Format, Status, \
    SourcePackage
from .services import filemanager, store

logger = logging.getLogger(__name__)


class NoSuchTask(RuntimeError):
    """A request was made for a non-existant task."""


class TaskCreationFailed(RuntimeError):
    """An extraction task could not be created."""


def create_compilation_task(source_id: str, checksum: str,
                            output_format: Format = Format.PDF,
                            preferred_compiler: Optional[str] = None,
                            token: Optional[str] = None) -> str:
    """
    Create a new compilation task.

    Parameters
    ----------
    source_id : str
        Unique identifier for the source being compiled.
    checksum : str
        The checksum for the source package. This is used to differentiate
        compilation tasks.
    output_format: Format
        The desired output format. Default: Format.PDF.
    preferred_compiler : str

    Returns
    -------
    str
        The identifier for the created compilation task.
    """
    task_id = get_task_id(source_id, checksum, output_format)
    try:
        do_compile.apply_async(
            (source_id, checksum),
            {'output_format': output_format.value,
             'preferred_compiler': preferred_compiler,
             'token': token},
            task_id=task_id
        )
        logger.info('compile: started processing as %s' % task_id)
    except Exception as e:
        logger.error('Failed to create task: %s', e)
        raise TaskCreationFailed('Failed to create task: %s', e) from e
    return task_id


def get_compilation_task(source_id: str, checksum: str,
                         output_format: Format = Format.PDF) \
        -> CompilationStatus:
    """
    Get the status of an extraction task.

    Parameters
    ----------
    source_id : str
        Unique identifier for the source being compiled.
    checksum : str
        The checksum for the source package. This is used to differentiate
        compilation tasks.
    output_format: Format
        The desired output format. Default: Format.PDF.

    Returns
    -------
    :class:`ExtractionTask`

    """
    task_id = get_task_id(source_id, checksum, output_format)
    result = do_compile.AsyncResult(task_id)
    data = {
        'source_id': source_id,
        'checksum': checksum,
        'output_format': output_format
    }
    if result.status == 'PENDING':
        raise NoSuchTask('No such task')
    elif result.status in ['SENT', 'STARTED', 'RETRY']:
        data['status'] = Status.IN_PROGRESS
    elif result.status == 'FAILURE':
        data['status'] = Status.FAILED
    elif result.status == 'SUCCESS':
        _result: Dict[str, str] = result.result
        if 'status' in _result:
            data['status'] = Status(_result['status'])
        else:
            data['status'] = Status.COMPLETED
        data['reason'] = _result.get('reason')
    return CompilationStatus(task_id=task_id, **data)


@after_task_publish.connect
def update_sent_state(sender=None, headers=None, body=None, **kwargs):
    """Set state to SENT, so that we can tell whether a task exists."""
    task = celery_app.tasks.get(sender)
    backend = task.backend if task else celery_app.backend
    backend.store_result(headers['id'], None, "SENT")


@celery_app.task
def do_compile(source_id: str, checksum: str,
               output_format: str = 'pdf',
               preferred_compiler: Optional[str] = None,
               token: Optional[str] = None) -> dict:
    """
    Retrieve a source package, compile to something, and store the result.

    Executed by the async worker on a completely separate machine (let's
    assume) from the compiler web service API.

    Parameters
    ------------
    source_id: str
        Required. The upload to retrieve.
    checksum : str
        The checksum for the source package. This is used to differentiate
        compilation tasks.
    output_format: str
        The desired output format. Default: "pdf". Other potential values:
        "dvi", "html", "ps"
    preferred_compiler: str
        The preferred tex compiler for use with the source package.

    """
    output_format = Format(output_format)

    container_source_root = current_app.config['CONTAINER_SOURCE_ROOT']
    verbose = current_app.config['VERBOSE_COMPILE']
    source_dir = tempfile.mkdtemp(dir=container_source_root)
    task_id = get_task_id(source_id, checksum, output_format)

    status = {
        'task_id': task_id,
        'source_id': source_id,
        'output_format': output_format,
        'checksum': checksum
    }

    try:
        filemanager.set_auth_token(token)
        source = filemanager.get_source_content(source_id, save_to=source_dir)
        logger.debug(f"{source_id} etag: {source.etag}")
    except filemanager.NotFound as e:
        reason = 'Could not retrieve a matching source package'
        stat = CompilationStatus(status=Status.FAILED, reason=reason, **status)
        return stat.to_dict()

    """
    if source.etag != checksum:
        logger.debug('source: %s; expected: %s', source.etag, checksum)
        reason = 'Source etag does not match requested etag'
        stat = CompilationStatus(status=Status.FAILED, reason=reason, **status)
        return stat.to_dict()
    """

    # 2. Generate the compiled files
    o_path, log_path = compile_source(source, output_format=output_format,
                                      verbose=verbose,
                                      tex_tree_timestamp=checksum)

    compile_status = CompilationStatus(
        status=Status.COMPLETED if o_path is not None else Status.FAILED,
        **status
    )

    # Store the result.
    try:
        _store_compilation_result(compile_status, o_path, log_path)
    except RuntimeError as e:
        stat = CompilationStatus(status=Status.FAILED, reason=str(e), **status)
        return stat.to_dict()

    # Clean up!
    try:
        shutil.rmtree(source_dir)
        logger.debug('Cleaned up %s', source_dir)
        #logger.debug('skipping cleanup of %s', source_dir)
    except Exception as e:
        logger.error('Could not clean up %s: %s', source_dir, e)
    return compile_status.to_dict()


def _store_compilation_result(status: CompilationStatus,
                              output_path: Optional[str],
                              log_path: Optional[str]) -> None:
    if output_path is not None:
        try:
            with open(output_path, 'rb') as f:
                store.store(CompilationProduct(stream=f, status=status))
        except Exception as e:  # TODO: look at exceptions in object store.
            raise RuntimeError('Failed to store result') from e

    if log_path is not None:
        try:
            with open(log_path, 'rb') as f:
                store.store_log(CompilationProduct(stream=f, status=status))
        except Exception as e:  # TODO: look at exceptions in object store.
            raise RuntimeError('Failed to store result') from e
    store.set_status(status)


# TODO: rename []_dvips_flag parameters when we figure out what they mean.
# TODO: can we get rid of any of these?
def compile_source(source: SourcePackage,
                   output_format: str = 'pdf', add_stamp: bool = True,
                   timeout: int = 600, add_psmapfile: bool = False,
                   P_dvips_flag: bool = False, dvips_layout: str = 'letter',
                   D_dvips_flag: bool = False,
                   id_for_decryption: Optional[str] = None,
                   tex_tree_timestamp = None,
                   verbose: bool = True) \
        -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Compile a TeX source package."""
    # We need the path to the directory container the source package on the
    # host machine, so that we can correctly mount the volume in the
    # converter container. We are assuming that the image is not running in
    # the same container as this worker application.
    source_dir, fname = os.path.split(source.stream)
    image = current_app.config['COMPILER_DOCKER_IMAGE']
    host_source_root = current_app.config['HOST_SOURCE_ROOT']
    container_source_root = current_app.config['CONTAINER_SOURCE_ROOT']
    leaf_path = source_dir.split(container_source_root, 1)[1].strip('/')
    host_source_dir = os.path.join(host_source_root, leaf_path)
    logger.debug('source_dir: %s', source_dir)
    logger.debug('host_source_root: %s', host_source_root)
    logger.debug('container_source_root: %s', container_source_root)
    logger.debug('leaf_path: %s', leaf_path)
    logger.debug('host_source_dir: %s', host_source_dir)
    logger.debug('got image %s', image)

    args = [
        '-S /autotex',
        f'-p {source.source_id}',
        f'-f {output_format}',  # This doesn't do what we think it does.
        f'-T {timeout}',
        f'-t {dvips_layout}',
        '-q',
    ]
    if verbose:
        args.append('-v')
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
    if tex_tree_timestamp is not None:
        args.append(f'-U {tex_tree_timestamp}')

    logger.debug('run image %s with args %s', image, args)
    run_docker(image, args=args,
               volumes=[(host_source_dir, '/autotex')])

    # Now we have to figure out what went right or wrong.
    ext = Format(output_format).ext

    cache = os.path.join(source_dir, 'tex_cache')
    try:
        # The converter image has some heuristics for naming (e.g. adding a
        # version affix). But at the end of the day there should be only one
        # file in the format that we requested, so that's as specific as we
        # should need to be.
        cache_results = [fp for fp in os.listdir(cache) if fp.endswith(f'.{ext}')]
        oname = cache_results[0]
        output_path = os.path.join(cache, oname)
    except IndexError:  # The expected output isn't here.
        # Normally I'd prefer to raise an exception if the compilation failed,
        # but we still have work to do.
        output_path = None
    # There are all kinds of ways in which compilation can fail. In many cases,
    # we'll have log output even if the compilation failed, and we don't want
    # to ignore that output.
    tex_log_path = os.path.join(source_dir, 'tex_logs', 'auto_gen_ps.log')
    return output_path, tex_log_path if os.path.exists(tex_log_path) else None


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
    # opt_user = '-u {}'.format(os.getuid())
    opt_volumes = ' '.join(['-v {}:{}'.format(hd, cd) for hd, cd in volumes])
    opt_ports = ' '.join(['-p {}:{}'.format(hp, cp) for hp, cp in ports])
    cmd = 'docker run --rm {} {} {} /bin/autotex.pl {}'.format(
        opt_ports, opt_volumes, image, ' '.join(args)
    )
    logger.debug('Full compile command: %s', cmd)
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=True)

    logger.error('Docker exited with %i', result.returncode)
    logger.error('STDOUT: %s', result.stdout)
    logger.error('STDERR: %s', result.stderr)


def get_task_id(source_id: str, checksum: str, output_format: Format) -> str:
    """Generate a key for a source_id/checksum/format combination."""
    return f"{source_id}::{checksum}::{output_format.value}"
