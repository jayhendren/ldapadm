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

def runLdapadm(*args, **kwargs):
    # runLdapadm() returns tuple (stdout, stderr, exitcode) of ldapadm output

    use_default_config = kwargs.get('use_default_config', True)
    if use_default_config:
        args = ('-c', conf_path) + args

    cmd = [os.path.join(proj_root_dir, 'src/ldapadm.py')] + list(args)
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

    def assertLdapadmSucceeds(self, *args, **kwargs):
        self.assertEqual(runLdapadm(*args, **kwargs)[2], 0)

    def assertLdapadmFails(self, *args, **kwargs):
        self.assertNotEqual(runLdapadm(*args, **kwargs)[2], 0)

class LdapadmBasicTests(LdapadmTest):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        self.assertLdapadmFails(use_default_config=False)

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

        def verifyOutput(output, object, search_term):
            output_obj = yaml.load(output[0])[search_term]
            filtered_obj = {k:object[1].get(k) \
                            for k in conf['user']['display']}
            self.assertEqual(output_obj, filtered_obj)

        def verifyCanGetUser(search_term):
            output = getOutput(search_term)
            object = getObject(search_term)
            verifyOutput(output, object, search_term)

        def verifyCannotGetUser(search_term):
            self.assertLdapadmFails(search_term)

        for user in ('bogus', 'totallynotauser'):
            verifyCannotGetUser(user)
        for user in ('admin', 'manager', 'employee', 'helpdesk'):
            verifyCanGetUser(user)
