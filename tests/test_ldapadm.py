import os
import subprocess
import yaml
import unittest
from src.ldapobjectmanager import LDAPObjectManager, auth

proj_root_dir = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
conf_path = os.path.join(proj_root_dir, 'tests/ldapadm-test.conf.yaml')

def parseConf():
    return yaml.load(file(conf_path, 'r'))

conf = parseConf()

def runLdapadm(*args):
    # this function returns tuple (stdout, stderr, exitcode) of ldapadm output
    cmd = [os.path.join(proj_root_dir, 'scripts/ldapadm.py')] + list(args)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    result =  proc.communicate()
    # if proc.returncode != 0: raise subprocess.CalledProcessError('', '')
    return result + (proc.returncode,)

def getLOM():
    return LDAPObjectManager(conf['uri'], auth.simple, user=conf['username'],
                             password=conf['password'])

class LdapadmTest(unittest.TestCase):

    def setUp(self):
        self.lom = getLOM()

    def assertLdapadmSucceeds(self, *args):
        self.assertEqual(runLdapadm(*args)[2], 0)

    def assertLdapadmFails(self, *args):
        self.assertNotEqual(runLdapadm(*args)[2], 0)

class LdapadmBasicTests(LdapadmTest):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        self.assertLdapadmFails()

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(runLdapadm("-h")[0], r'usage:')
        self.assertRegexpMatches(runLdapadm("--help")[0], r'usage:')

class LdapadmGetTests(LdapadmTest):

    def testGetWithBadArgumentsReturnsError(self):
        self.assertLdapadmFails('get')
        self.assertLdapadmFails('get', 'bogus')

    def testSimpleGetUser(self):

        # get user results must contain 'attribute: value'
        # for all display attributes listed in configuration

        def getOutput(search_term):
            return runLdapadm('get', 'user', search_term)

        def getObject(search_term):
            return self.lom.getSingle(conf['user']['base'],
                '%s=%s' %(conf['user']['identifier'], search_term))

        def verifyOutput(output, object):
            for attr in conf['user']['display']:
                for value in object[1][attr]:
                    regex = r'%s\s*:\s*%s' %(attr, value)
                    self.assertRegexpMatches(output[0], regex)

        def verifyCanGetUser(search_term):
            output = getOutput(search_term)
            object = getObject(search_term)
            verifyOutput(output, object)

        def verifyCannotGetUser(search_term):
            self.assertLdapadmFails(search_term)

        for user in ('bogus', 'totallynotauser'):
            verifyCannotGetUser(user)
        for user in ('admin', 'manager', 'employee', 'helpdesk'):
            verifyCanGetUser(user)
