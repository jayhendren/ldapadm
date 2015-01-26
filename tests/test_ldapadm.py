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

    raise_on_error = kwargs.get('raise_on_error', True)
    raise_on_success = kwargs.get('raise_on_success', False)
    use_default_config = kwargs.get('use_default_config', True)
    if raise_on_success: raise_on_error = False

    if use_default_config:
        args = ('-c', conf_path) + args

    cmd = [os.path.join(proj_root_dir, 'src/ldapadm.py')] + list(args)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    result = proc.communicate()
    result = result + (proc.returncode,)
    # if proc.returncode != 0: raise subprocess.CalledProcessError('', '')
    if (raise_on_error and proc.returncode != 0) or \
       (raise_on_success and proc.returncode == 0):
        msg = "Ldapadm unexpectedly exited with nonzero return code."
        if raise_on_success:
            msg = "Ldapadm unexpectedly ran successfully."
        raise RuntimeError( "%s\n" % msg + "args: %s\n" % (args,) + \
                           "Stdout:\n%s\nStderr:\n%s\nErr: %s"  % result)
    return result

def getLOM():
    return LDAPObjectManager(conf['uri'], auth.simple, user=conf['username'],
                             password=conf['password'])

class LdapadmTest(unittest.TestCase):

    def setUp(self):
        self.lom = getLOM()

    def assertLdapadmSucceeds(self, *args, **kwargs):
        runLdapadm(*args, **kwargs)

    def assertLdapadmFails(self, *args, **kwargs):
        runLdapadm(*args, raise_on_success=True, **kwargs)

    def getOutput(self, type, search_term):
        return runLdapadm('get', type, search_term)

    def getObject(self, type, search_term):
        return self.lom.getSingle(conf[type]['base'],
            '%s=%s' %(conf[type]['identifier'], search_term))

    def verifyOutput(self, output, object, type, search_term):
        output_obj = yaml.load(output[0])[search_term]
        filtered_obj = {k:object[1].get(k) \
                        for k in conf[type]['display']}
        self.assertEqual(output_obj, filtered_obj)

    def verifyCanGet(self, type, search_term):
        output = self.getOutput(type, search_term)
        object = self.getObject(type, search_term)
        self.verifyOutput(output, object, type, search_term)

    def verifyCannotGet(self, type, search_term):
        self.assertLdapadmFails('get', type, search_term)

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

        for user in ('bogus', 'totallynotauser'):
            self.verifyCannotGet('user', user)
        for user in ('admin', 'manager', 'employee', 'helpdesk'):
            self.verifyCanGet('user', user)

    def testSimpleGetUnixGroup(self):

        for group in ('bogus', 'totallynotagroup'):
            self.verifyCannotGet('group', group)
        for group in ('admins', 'managers', 'employees', 'helpdesk'):
            self.verifyCanGet('group', group)

    def testSimpleGetAccessGroup(self):

        for access in ('bogus', 'totallynotaaccess'):
            self.verifyCannotGet('access', access)
        for access in ('admins', 'managers', 'employees', 'helpdesk'):
            self.verifyCanGet('access', access)
