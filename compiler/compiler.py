r"""
Dispatching and execution of compilation tasks.

Parameters supported by autotex "converter" image::

     -C cache directory [defaults to paper/format specific directory in PS_CACHE]
     -D pass through for -D dvips flag
     -f output format, only sensible use is -f fInm for pdf generation
     -u add a psmapfile to dvips command "-u +psmapfile"
     -h print usage
     -k do not delete temporary directory
     -P pass through for -P dvips flag
     -p id of paper to process (pre 2007 archive/papernum or new numerical id
        yymm.\\d{4,5}) (required!)
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


We're going to use:

- ``-f`` output format, only sensible use is -f fInm for pdf generation (fInm,
  dvi, ps)
- ``-p`` id of paper to process (pre 2007 archive/papernum or new numerical id
  yymm.\\d{4,5}) (required!)
- ``-s`` do not add stamp to PostScript
- ``-T`` override the default AUTOTEX_TIMEOUT setting with user value
- ``-u`` add a psmapfile to dvips command "-u +psmapfile"
- ``-P`` pass through for -P dvips flag
- ``-t`` pass through for -t dvips flag (letter, legal, ledger, a4, a3, landscape)
- ``-D`` pass through for -D dvips flag
- ``-d`` id to use for decrytion (overrides default to -p id)

Always do this:

- ``-q`` quiet - don't send emails to tex_admin (not the inverse of verbose!)
- ``-Y`` don't copy PostScript or PDF to cache

"""

import os
from typing import List, Dict, Optional, Tuple, Callable, Any, Mapping, \
    Hashable
from functools import wraps
from itertools import chain
import subprocess
import tarfile
import shutil
import tempfile
from tempfile import TemporaryDirectory

from flask import current_app

from celery.result import AsyncResult
from celery.signals import after_task_publish

import docker
from docker import DockerClient
from docker.errors import ContainerError, APIError
from requests.exceptions import ConnectionError

from arxiv.base import logging
from arxiv.integration.api import exceptions

from celery.task.control import inspect
from .celery import celery_app
from .domain import Product, Task, Format, Status, \
    SourcePackage, Reason
from .services import Store
from .services import FileManager

logger = logging.getLogger(__name__)

ProcessResult = Tuple[int, str, str]


class NoSuchTask(RuntimeError):
    """A request was made for a non-existant task."""


class TaskCreationFailed(RuntimeError):
    """An extraction task could not be created."""


class CorruptedSource(RuntimeError):
    """The source content is corrupted."""


class AuthorizationFailed(RuntimeError):
    """The request was not authorized."""


def is_available(await_result: bool = False) -> bool:
    """Verify that we can start compilations."""
    logger.debug('check connection to task queue')
    try:
        task = do_nothing.apply_async()
    except Exception:
        logger.debug('could not connect to task queue')
        return False
    logger.debug('connection to task queue ok')
    if await_result:
        try:
            logger.debug('waiting for task result')
            task.get()    # Blocks until result is available.
        except Exception as e:
            logger.error('Encounted exception while awaiting result: %s', e)
            return False
    return True


def start_compilation(source_id: str, checksum: str,
                      stamp_label: Optional[str] = None,
                      stamp_link: Optional[str] = None,
                      output_format: Format = Format.PDF,
                      preferred_compiler: Optional[str] = None,
                      token: Optional[str] = None,
                      owner: Optional[str] = None) -> str:
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
    task_id = _get_task_id(source_id, checksum, output_format)
    try:
        do_compile.apply_async(
            (source_id, checksum),
            {'output_format': output_format.value,
             'stamp_label': stamp_label,
             'stamp_link': stamp_link,
             'preferred_compiler': preferred_compiler,
             'token': token,
             'owner': owner},
            task_id=task_id
        )
        logger.info('compile: started processing as %s' % task_id)
    except Exception as e:
        logger.error('Failed to create task: %s', e)
        raise TaskCreationFailed('Failed to create task: %s', e) from e

    store = Store.current_session()
    store.set_status(Task(source_id=source_id,
                          checksum=checksum,
                          output_format=output_format,
                          status=Status.IN_PROGRESS,
                          task_id=task_id,
                          owner=owner))
    return task_id


def get_task(source_id: str, checksum: str,
             output_format: Format = Format.PDF) -> Task:
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
    :class:`Task`

    """
    task_id = _get_task_id(source_id, checksum, output_format)
    result = do_compile.AsyncResult(task_id)
    task_status = Status.IN_PROGRESS
    owner: Optional[str] = None
    reason = Reason.NONE
    if result.status == 'PENDING':
        raise NoSuchTask(f'No such task: {task_id}')
    elif result.status in ['SENT', 'STARTED', 'RETRY']:
        task_status = Status.IN_PROGRESS
    elif result.status == 'FAILURE':
        task_status = Status.FAILED
    elif result.status == 'SUCCESS':
        _result: Dict[str, str] = result.result
        if 'status' in _result:
            task_status = Status(_result['status'])
        else:
            task_status = Status.COMPLETED
        reason = Reason(_result.get('reason'))
        if 'owner' in _result:
            owner = _result['owner']
    return Task(source_id=source_id,
                checksum=checksum,
                output_format=output_format,
                task_id=task_id,
                status=task_status,
                reason=reason,
                owner=owner)


@after_task_publish.connect
def update_sent_state(sender: Optional[Hashable] = None,
                      headers: Optional[Mapping] = None,
                      body: Optional[Any] = None,
                      **kwargs: Any) -> None:
    """Set state to SENT, so that we can tell whether a task exists."""
    task = celery_app.tasks.get(sender)
    backend = task.backend if task else celery_app.backend
    if headers is not None:
        backend.store_result(headers['id'], None, "SENT")


@celery_app.task
def do_nothing() -> None:
    """Dummy task used to check the connection to the queue."""
    return


@celery_app.task
def do_compile(source_id: str, checksum: str,
               stamp_label: Optional[str],
               stamp_link: Optional[str],
               output_format: str = 'pdf',
               preferred_compiler: Optional[str] = None,
               token: Optional[str] = None,
               owner: Optional[str] = None) -> dict:
    """
    Retrieve a source package, compile to something, and store the result.

    Executed by the async worker on a completely separate machine (let's
    assume) from the compiler web service API.

    Parameters
    ----------
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
        Not supported.
    token : str
        Auth token to pass with subrequests to backend services.

    """
    logger.debug("do compile for %s @ %s to %s", source_id, checksum,
                 output_format)
    fm = FileManager.current_session()

    container_source_root = current_app.config['CONTAINER_SOURCE_ROOT']
    verbose = current_app.config['VERBOSE_COMPILE']
    source_dir = tempfile.mkdtemp(dir=container_source_root)
    task_id = _get_task_id(source_id, checksum, Format(output_format))
    out_path: Optional[str] = None
    log_path: Optional[str] = None
    size_bytes = 0
    _format = Format(output_format)

    stat = None
    try:
        source = fm.get_source_content(source_id, token, save_to=source_dir)
        logger.debug(f"{source_id} etag: {source.etag}")
    except (exceptions.RequestUnauthorized, exceptions.RequestForbidden):
        description = "There was a problem authorizing your request."
        stat = Task(status=Status.FAILED,
                    reason=Reason.AUTHORIZATION,
                    description=description,
                    source_id=source_id,
                    output_format=_format,
                    checksum=checksum,
                    task_id=task_id,
                    owner=owner,
                    size_bytes=size_bytes)
    except exceptions.ConnectionFailed:
        description = "There was a problem retrieving your source files."
        stat = Task(status=Status.FAILED,
                    reason=Reason.NETWORK,
                    description=description,
                    source_id=source_id,
                    output_format=_format,
                    checksum=checksum,
                    task_id=task_id,
                    owner=owner,
                    size_bytes=size_bytes)
    except exceptions.NotFound:
        description = 'Could not retrieve a matching source package'
        stat = Task(status=Status.FAILED,
                    reason=Reason.MISSING,
                    description=description,
                    source_id=source_id,
                    output_format=_format,
                    checksum=checksum,
                    task_id=task_id,
                    owner=owner,
                    size_bytes=size_bytes)

    """
    if source.etag != checksum:
        logger.debug('source: %s; expected: %s', source.etag, checksum)
        reason = 'Source etag does not match requested etag'
        stat = Task(status=Status.FAILED, reason=reason, **status)
        return stat.to_dict()
    """

    # 2. Generate the compiled files

    if not stat:
        compile = Compiler()
        if not compile.is_available():
            stat = Task(status=Status.FAILED,
                        reason=Reason.DOCKER,
                        source_id=source_id,
                        output_format=_format,
                        checksum=checksum,
                        task_id=task_id,
                        owner=owner,
                        size_bytes=size_bytes)

        try:
            out_path, log_path = compile(source, stamp_label=stamp_label,
                                         stamp_link=stamp_link,
                                         output_format=_format,
                                         verbose=verbose)
            if out_path is not None:
                size_bytes = _file_size(out_path)
        except CorruptedSource:
            stat = Task(status=Status.FAILED,
                        reason=Reason.CORRUPTED,
                        source_id=source_id,
                        output_format=_format,
                        checksum=checksum,
                        task_id=task_id,
                        owner=owner,
                        size_bytes=size_bytes)
        except RuntimeError:
            stat = Task(status=Status.FAILED,
                        reason=Reason.DOCKER,
                        source_id=source_id,
                        output_format=_format,
                        checksum=checksum,
                        task_id=task_id,
                        owner=owner,
                        size_bytes=size_bytes)
    if not stat:
        if out_path is not None:
            stat = Task(status=Status.COMPLETED,
                        source_id=source_id,
                        output_format=_format,
                        checksum=checksum,
                        task_id=task_id,
                        owner=owner,
                        size_bytes=size_bytes)
        else:
            stat = Task(status=Status.FAILED,
                        reason=Reason.COMPILATION,
                        source_id=source_id,
                        output_format=_format,
                        checksum=checksum,
                        task_id=task_id,
                        owner=owner,
                        size_bytes=size_bytes)
    # Store the result.
    try:
        _store_compilation_result(stat, out_path, log_path)
    except RuntimeError as e:
        stat = Task(status=Status.FAILED,
                    reason=Reason.STORAGE,
                    description=str(e),
                    source_id=source_id,
                    output_format=_format,
                    checksum=checksum,
                    task_id=task_id,
                    owner=owner,
                    size_bytes=size_bytes)

    # Clean up!
    try:
        shutil.rmtree(source_dir)
        logger.debug('Cleaned up %s', source_dir)
    except Exception as e:
        logger.error('Could not clean up %s: %s', source_dir, e)
    return stat.to_dict()


def _store_compilation_result(status: Task, out_path: Optional[str],
                              log_path: Optional[str]) -> None:
    """Store the status and output (including log) of compilation."""
    logger.debug('_store_compilation_result: %s %s', out_path, log_path)
    store = Store.current_session()
    if out_path is not None:
        try:
            with open(out_path, 'rb') as f:
                store.store(Product(stream=f, task=status))
        except Exception as e:  # TODO: look at exceptions in object store.
            raise RuntimeError('Failed to store result') from e

    if log_path is not None:
        try:
            with open(log_path, 'rb') as f:
                store.store_log(Product(stream=f, task=status))
        except Exception as e:  # TODO: look at exceptions in object store.
            raise RuntimeError('Failed to store result') from e
    store.set_status(status)
    logger.debug('_store_compilation_result: ok')


class Compiler:
    """Integrates with Docker to perform compilation using converter image."""

    def is_available(self, **kwargs: Any) -> bool:
        """Make sure that we can connect to the Docker API."""
        try:
            self._new_client().info()
        except (APIError, ConnectionError) as e:
            logger.error('Error when connecting to Docker API: %s', e)
            return False
        return True

    def _new_client(self) -> DockerClient:
        """Make a new Docker client."""
        return DockerClient(current_app.config['DOCKER_HOST'])

    @property
    def image(self) -> Tuple[str, str, str]:
        """Get the name of the image used for compilation."""
        image_name = current_app.config['CONVERTER_DOCKER_IMAGE']
        try:
            image_name, image_tag = image_name.split(':', 1)
        except ValueError:
            image_tag = 'latest'
        return f'{image_name}:{image_tag}', image_name, image_tag

    def _pull_image(self, client: Optional[DockerClient] = None) -> None:
        """Tell the Docker API to pull our converter image."""
        if client is None:
            client = self._new_client()
        _, name, tag = self.image
        client.images.pull(name, tag)

    # TODO: rename []_dvips_flag parameters when we figure out what they mean.
    # TODO: can we get rid of any of these?
    def __call__(self, source: SourcePackage, stamp_label: Optional[str],
                 stamp_link: Optional[str], output_format: Format = Format.PDF,
                 add_stamp: bool = True, timeout: int = 600,
                 add_psmapfile: bool = False, P_dvips_flag: bool = False,
                 dvips_layout: str = 'letter', D_dvips_flag: bool = False,
                 id_for_decryption: Optional[str] = None,
                 tex_tree_timestamp: Optional[str] = None,
                 verbose: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """
        Compile a TeX source package.

        Parameters
        ----------
        source : :class:`.SourcePackage`
            TeX source package to compile.
        stamp_label : str
            Text used for the stamp/watermark on the left margin of the PDF.
        stamp_link : str
            URL for the hyperlink target of the stamp/watermark.
        output_format : :class:`.Format`
            Only currently supported format is :const:`.Format.PDF`.
        add_stamp : bool
            Whether or not to add the stamp/watermark (default True).
        timeout : int
            Value for the ``AUTOTEX_TIMEOUT`` parameter (seconds).
        add_psmapfile : bool
            If True, adds a psmapfile to dvips command "-u +psmapfile"
            (default False).
        P_dvips_flag : bool
        dvips_layout : str
            Default is ``'letter'``.
        D_dvips_flag : bool
        id_for_decryption : str or None
            If provided, id to use for decrytion (overrides default to -p id).
        tex_tree_timestamp : str or None
        verbose : bool
            Compile in verbose mode (default True).

        Returns
        -------
        str
            Path to the created PDF file.
        str
            Path to the TeX compilation log file.

        """
        # We need the path to the directory container the source package on the
        # host machine, so that we can correctly mount the volume in the
        # converter container. We are assuming that the image is not running in
        # the same container as this worker application.
        source_dir, fname = os.path.split(source.path)
        host_source_root = current_app.config['HOST_SOURCE_ROOT']
        container_source_root = current_app.config['CONTAINER_SOURCE_ROOT']
        leaf_path = source_dir.split(container_source_root, 1)[1].strip('/')
        host_source_dir = os.path.join(host_source_root, leaf_path)
        out_path: Optional[str]

        options = [
            (True, '-S /autotex'),
            (True, f'-p {source.source_id}'),
            (True, f'-f {output_format.value}'),  # Doesn't do what it seems.
            (stamp_label is not None, f'-l "{stamp_label}"'),
            (stamp_link is not None, f'-L "{stamp_link}"'),
            (True, f'-T {timeout}'),
            (True, f'-t {dvips_layout}'),
            (True, '-q'),
            (verbose, '-v'),
            (not add_stamp, '-s'),
            (add_psmapfile, '-u'),
            (P_dvips_flag, '-P'),
            (id_for_decryption is not None, f'-d {id_for_decryption}'),
            (tex_tree_timestamp is not None, f'-U {tex_tree_timestamp}')
        ]

        args = [arg for opt, arg in options if opt]

        client = self._new_client()
        image, _, _ = self.image
        try:
            self._pull_image(client)
            volumes = {host_source_dir: {'bind': '/autotex', 'mode': 'rw'}}
            log: bytes = client.containers.run(image, ' '.join(args),
                                               volumes=volumes)
        except (ContainerError, APIError) as e:
            raise RuntimeError(f'Compilation failed for {source.path}') from e

        # Now we have to figure out what went right or wrong.
        ext = Format(output_format).ext

        cache = os.path.join(source_dir, 'tex_cache')

        # The converter image has some heuristics for naming (e.g. adding a
        # version affix). But at the end of the day there should be only one
        # file in the format that we requested, so that's as specific as we
        # should need to be.
        oname: Optional[str] = None
        for fname in os.listdir(cache):
            if fname.endswith(f'.{ext}'):
                oname = fname
                break
        if oname is None:       # The expected output isn't here.
            out_path = None     # But we still have work to do.
        else:
            out_path = os.path.join(cache, oname)

        # There are all kinds of ways in which compilation can fail. In many
        # cases, we'll have log output even if the compilation failed, and we
        # don't want to ignore that output.
        tex_log_path = os.path.join(source_dir, 'tex_logs', 'autotex.log')

        # Sometimes the log file does not get written, in which case we can
        # fall back to the stdout from the converter subprocess.
        if not os.path.exists(tex_log_path):
            log_dir = os.path.split(tex_log_path)[0]
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            with open(tex_log_path, 'wb') as f:
                f.write(log)

        return out_path, tex_log_path


def _get_task_id(source_id: str, checksum: str, output_format: Format) -> str:
    """Generate a key for a source_id/checksum/format combination."""
    return f"{source_id}/{checksum}/{output_format.value}"


def _file_size(path: str) -> int:
    return os.path.getsize(path)
