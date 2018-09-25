import os
import os.path
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from typing import Optional, Tuple

from flask import current_app
from arxiv.base import logging

from .domain import CompilationProduct

import compiler.services.filemanager as filemanager

logger = logging.getLogger(__name__)

def compile_upload(upload_id: str, output_format: str='pdf', 
                   preferred_compiler: Optional[str]=None):
    """
    Retrieves an upload, submits to the converter service, uploads results.

    More or less, the ``main()`` function for compiler. It operates in a
    three-step process:
    1.  Retrieve the source package for ``upload_id`` from the file management
        service.
    2.  Use the ``preferred_compiler`` to generate ``output_format``.
    3.  Upload the results.

    Parameters
    ------------
    upload_id: str
        Required. The upload to retrieve.
    output_format: str
        The desired output format. Default: "pdf". Other potential values:
        "dvi", "html", "ps"
    preferred_compiler: str
        The preferred tex compiler for use with the source package.
    """
    source_package = filemanager.get_upload_content(upload_id)

    # 2. Generate the compiled files
    # 3. Upload the results to output_endpoint
    with TemporaryDirectory(prefix='arxiv') as source_dir,\
         TemporaryDirectory(prefix='arxiv') as output_dir:
        with tarfile.open(fileobj=source_package.stream, mode='r:gz') as tar: # type: ignore
            tar.extractall(path=source_dir)

        # 2. Generate the compiled files
        compile_source(source_dir, output_dir)

        # 3. Upload the results to output_endpoint
        # 3a. gather the candidate products based on output_format
        products = [f for f in os.listdir(output_dir) 
                        if f.endswith(output_format)]

        if len(products) != 1:
            raise RuntimeWarning("Multiple compilation products")

        # TODO: 3b. upload the output somewhere(?)



def compile_source(source_dir: str, output_dir: str, image: Optional[str]=None):
    if image is None:
        image = current_app.config['COMPILER_DOCKER_IMAGE']

    run_docker(image, volumes=[(source_dir, '/src'), (output_dir, '/out')])


def run_docker(image: str, volumes: list = [], ports: list = [],
               args: str = '', daemon: bool = False) -> subprocess.CompletedProcess:
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
