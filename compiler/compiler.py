import os.path
import subprocess
import tarfile
from tempfile import TemporaryDirectory

from compiler.services.filemanager import FileManagementService

ENDPOINT = ''

def compile_upload(upload_id: str):
    fms = FileManagementService(ENDPOINT)
    _, headers = fms.check_upload_content_exists(upload_id)
    etag = headers['ETag']

    body, headers = fms.get_upload_content(upload_id)

    with TemporaryDirectory(prefix='arxiv') as source_dir,
         TemporaryDirectory(prefix='arxiv') as output_dir:
        with tarfile.open(fileobj=body) as tar:
            tar.extractall(path=source_dir)

        compile_source(source_dir, output_dir)

        # TODO: upload the output somewhere(?)


def compile_source(source_dir: str, output_dir: str, image: Optional[str]):
    if image is None:
        image = current_app.config['COMPILER_DOCKER_IMAGE']

    run_docker(image, volumes=[(source_dir, '/src'), (output_dir '/out')])


def run_docker(image: str, volumes: list = [], ports: list = [],
               args: str = '', daemon: bool = False) -> Tuple[str, str]:
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
