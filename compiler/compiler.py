import os
import os.path
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from typing import Optional, Tuple

from flask import current_app
from arxiv.base import logging

from .domain import CompilationProduct, CompilationStatus

from compiler.services import filemanager, store

logger = logging.getLogger(__name__)


def compile(source_id: str, source_checksum: str, format: str = 'pdf',
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
    format: str
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
        try:
            product_path, log_path = compile_source(source_dir, output_dir,
                                                    format=format)
        except Exception as e:
            # TODO: what gets raised?
            raise RuntimeError('Compilation failed') from e

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


def compile_source(source_dir: str, output_dir: str,
                   format: str = 'pdf',
                   image: Optional[str] = None) -> Tuple[str, str]:
    """Compile a TeX source package."""
    if image is None:
        image = current_app.config['COMPILER_DOCKER_IMAGE']

    # TODO: specify format
    run_docker(image, volumes=[(source_dir, '/src'), (output_dir, '/out')])

    return (
        os.path.join(output_dir, 'test.pdf'),
        os.path.join(output_dir, 'test.log')
    )


def run_docker(image: str, volumes: list = [], ports: list = [],
               args: str = '', daemon: bool = False) \
        -> subprocess.CompletedProcess:
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
        opt_user, opt_ports, opt_volumes, image, args
    )
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, shell=True)
    if result.returncode:
        logger.error(f"Docker image call '{cmd}' exited {result.returncode}")
        logger.error(f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}")
        result.check_returncode()

    return result
