"""Tests for distutils.command.upload."""
import os
import unittest
import unittest.mock as mock
from urllib.request import HTTPError

from sql_mode.support import run_unittest

from distutils.command import upload as upload_mod
from distutils.command.upload import upload
from distutils.core import Distribution
from distutils.errors import DistutilsError
from distutils.log import ERROR, INFO

from distutils.tests.test_config import PYPIRC, BasePyPIRCCommandTestCase

PYPIRC_LONG_PASSWORD = """\
[distutils]

index-servers =
    server1
    server2

[server1]
username:me
password:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

[server2]
username:meagain
password: secret
realm:acme
repository:http://another.pypi/
"""


PYPIRC_NOPASSWORD = """\
[distutils]

index-servers =
    server1

[server1]
username:me
"""

class FakeOpen(object):

    def __init__(self, url, msg=None, code=None):
        self.url = url
        if not isinstance(url, str):
            self.req = url
        else:
            self.req = None
        self.msg = msg or 'OK'
        self.code = code or 200

    def getheader(self, name, default=None):
        return {
            'content-type': 'text/plain; charset=utf-8',
            }.get(name.lower(), default)

    def read(self):
        return b'xyzzy'

    def getcode(self):
        return self.code


class uploadTestCase(BasePyPIRCCommandTestCase):

    def setUp(self):
        super(uploadTestCase, self).setUp()
        self.old_open = upload_mod.urlopen
        upload_mod.urlopen = self._urlopen
        self.last_open = None
        self.next_msg = None
        self.next_code = None

    def tearDown(self):
        upload_mod.urlopen = self.old_open
        super(uploadTestCase, self).tearDown()

    def _urlopen(self, url):
        self.last_open = FakeOpen(url, msg=self.next_msg, code=self.next_code)
        return self.last_open

    def test_finalize_options(self):

        # new format
        self.write_file(self.rc, PYPIRC)
        dist = Distribution()
        cmd = upload(dist)
        cmd.finalize_options()
        for attr, waited in (('username', 'me'), ('password', 'secret'),
                             ('realm', 'pypi'),
                             ('repository', 'https://upload.pypi.org/legacy/')):
            self.assertEqual(getattr(cmd, attr), waited)

    def test_saved_password(self):
        # file with no password
        self.write_file(self.rc, PYPIRC_NOPASSWORD)

        # make sure it passes
        dist = Distribution()
        cmd = upload(dist)
        cmd.finalize_options()
        self.assertEqual(cmd.password, None)

        # make sure we get it as well, if another command
        # initialized it at the dist level
        dist.password = 'xxx'
        cmd = upload(dist)
        cmd.finalize_options()
        self.assertEqual(cmd.password, 'xxx')

    def test_upload(self):
        tmp = self.mkdtemp()
        path = os.path.join(tmp, 'xxx')
        self.write_file(path)
        command, pyversion, filename = 'xxx', '2.6', path
        dist_files = [(command, pyversion, filename)]
        self.write_file(self.rc, PYPIRC_LONG_PASSWORD)

        # lets run it
        pkg_dir, dist = self.create_dist(dist_files=dist_files)
        cmd = upload(dist)
        cmd.show_response = 1
        cmd.ensure_finalized()
        cmd.run()

        # what did we send ?
        headers = dict(self.last_open.req.headers)
        self.assertEqual(headers['Content-length'], '2162')
        content_type = headers['Content-type']
        self.assertTrue(content_type.startswith('multipart/form-data'))
        self.assertEqual(self.last_open.req.get_method(), 'POST')
        expected_url = 'https://upload.pypi.org/legacy/'
        self.assertEqual(self.last_open.req.get_full_url(), expected_url)
        self.assertTrue(b'xxx' in self.last_open.req.data)
        self.assertIn(b'protocol_version', self.last_open.req.data)

        # The PyPI response body was echoed
        results = self.get_logs(INFO)
        self.assertEqual(results[-1], 75 * '-' + '\nxyzzy\n' + 75 * '-')

    def test_upload_fails(self):
        self.next_msg = "Not Found"
        self.next_code = 404
        self.assertRaises(DistutilsError, self.test_upload)

    def test_wrong_exception_order(self):
        tmp = self.mkdtemp()
        path = os.path.join(tmp, 'xxx')
        self.write_file(path)
        dist_files = [('xxx', '2.6', path)]  # command, pyversion, filename
        self.write_file(self.rc, PYPIRC_LONG_PASSWORD)

        pkg_dir, dist = self.create_dist(dist_files=dist_files)
        tests = [
            (OSError('oserror'), 'oserror', OSError),
            (HTTPError('url', 400, 'httperror', {}, None),
             'Upload failed (400): httperror', DistutilsError),
        ]
        for exception, expected, raised_exception in tests:
            with self.subTest(exception=type(exception).__name__):
                with mock.patch('distutils.command.upload.urlopen',
                                new=mock.Mock(side_effect=exception)):
                    with self.assertRaises(raised_exception):
                        cmd = upload(dist)
                        cmd.ensure_finalized()
                        cmd.run()
                    results = self.get_logs(ERROR)
                    self.assertIn(expected, results[-1])
                    self.clear_logs()


def test_suite():
    return unittest.makeSuite(uploadTestCase)

if __name__ == "__main__":
    run_unittest(test_suite())
