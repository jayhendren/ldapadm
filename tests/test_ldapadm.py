import os
import subprocess
import unittest

def runLdapadm(*args):
    # a CalledProcessError will be raised if the exit code is not zero
    # this function returns stdout of ldapadm
    proj_root_dir = os.path.split(os.path.dirname(\
        os.path.realpath(__file__)))[0]
    cmd = [os.path.join(proj_root_dir, 'scripts/ldapadm.py')] + list(args)
    return subprocess.check_output(cmd)

class LdapadmBasicTests(unittest.TestCase):

    def testCanRunLdapadm(self):
        with self.assertRaises(subprocess.CalledProcessError):
            runLdapadm()

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(runLdapadm("-h"), r'usage:')
        self.assertRegexpMatches(runLdapadm("--help"), r'usage:')
