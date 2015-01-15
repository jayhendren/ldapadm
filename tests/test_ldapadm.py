import os
import subprocess
import unittest

def runLdapadm(args):
    # a CalledProcessError will be raised if the exit code is not zero
    # this function returns stdout of ldapadm
    proj_root_dir = os.path.split(os.path.dirname(\
        os.path.realpath(__file__)))[0]
    return subprocess.check_output(os.path.join(proj_root_dir,
        'scripts/ldapadm.py'))

class LdapadmBasicTests(unittest.TestCase):

    def testCanRunLdapadm(self):
        runLdapadm("")

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(runLdapadm("-h"), r'Usage:')
        self.assertRegexpMatches(runLdapadm("--help"), r'Usage:')
