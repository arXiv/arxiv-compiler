"""Tests for :mod:`compiler.compiler`."""

import importlib_resources
from tempfile import TemporaryDirectory
from unittest import TestCase, mock
from operator import itemgetter

import os.path
import subprocess

from arxiv import status

from .. import compiler
from .. import domain, util

class TestCompileUpload(TestCase):
    """:func:`compiler.compile_upload` compiles the upload."""

    @mock.patch(f'{compiler.__name__}.filemanager.get_upload_content')
    def test_compile_upload(self, mock_content):
        """Get info for an upload workspace that exists."""
        etag = 'asdf12345checksum'
        upload_id = '123456'
        content = importlib_resources.read_binary('compiler.tests', 'test.tar')
        product_content = importlib_resources.read_binary('compiler.tests', 'test.pdf')
            

        mock_content.return_value = domain.SourcePackage(
            source_id=upload_id,
            stream=domain.ResponseStream(content),
            etag=etag
        )


    @mock.patch(f'{compiler.__name__}.current_app')
    def test_compile_source(self, mock_app):
        content = importlib_resources.read_binary('compiler.tests', 'test.tar')
        product_content = importlib_resources.read_binary('compiler.tests', 'test.pdf')
        
        # compile the Dockerfile
        with importlib_resources.path('compiler.tests', 'Dockerfile') as dockerfile:
            DOCKER_IMAGE = 'arxiv-compiler-test'

            DOCKERFILE_DIR = os.path.dirname(dockerfile)
            cmd = f"docker build -t {DOCKER_IMAGE} {DOCKERFILE_DIR}"
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, shell=True)
            if result.returncode:
                raise RuntimeError(f"Could not compile {DOCKER_IMAGE}: {cmd}")
            
            # mock the current_app
            config_dict =  {'COMPILER_DOCKER_IMAGE': DOCKER_IMAGE}
            mock_app.return_value = mock.MagicMock(config=mock.MagicMock())
            mock_app.config.__getitem__.side_effect = config_dict.__getitem__

            # Create temporary directories and attempt to use the test Dockerfile
            with TemporaryDirectory(prefix='arxiv') as source_dir,\
                TemporaryDirectory(prefix='arxiv') as output_dir:

                with open(os.path.join(source_dir, "test.pdf"), 'wb') as outfile:
                    outfile.write(product_content)

                product = compiler.compile_source(source_dir, output_dir)
                self.assertIsInstance(product, domain.CompilationProduct)
                self.assertEqual(product.stream.read(), product_content)
