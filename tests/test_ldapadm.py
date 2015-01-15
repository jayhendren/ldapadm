import os
import subprocess
import unittest

def runLdapadm(*args):
    # a CalledProcessError will be raised if the exit code is not zero
    # this function returns tuple (stdout, stderr) of ldapadm output
    proj_root_dir = os.path.split(os.path.dirname(\
        os.path.realpath(__file__)))[0]
    cmd = [os.path.join(proj_root_dir, 'scripts/ldapadm.py')] + list(args)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    result =  proc.communicate()
    if proc.returncode != 0: raise subprocess.CalledProcessError('', '')
    return result

class LdapadmBasicTests(unittest.TestCase):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        with self.assertRaises(subprocess.CalledProcessError):
            runLdapadm()

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(runLdapadm("-h")[0], r'usage:')
        self.assertRegexpMatches(runLdapadm("--help")[0], r'usage:')

class LdapadmGetTests(unittest.TestCase):

    def testGetWithBadArgumentsReturnsError(self):
        with self.assertRaises(subprocess.CalledProcessError):
            runLdapadm('get')
        with self.assertRaises(subprocess.CalledProcessError):
            runLdapadm('get', 'bogus')
