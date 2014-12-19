import os
import subprocess
import unittest

class LdapadmBasicTests(unittest.TestCase):

    def testStub(self):
        proj_root_dir = os.path.split(os.path.dirname(\
            os.path.realpath(__file__)))[0]
        subprocess.call(os.path.join(proj_root_dir, 'scripts/ldapadm'))
