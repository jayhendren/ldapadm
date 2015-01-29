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

    def verifyOutput(self, output, object, type, search_term):
        output_obj = yaml.load(output[0])[search_term][1]
        filtered_obj = {k:object[1].get(k) \
                        for k in conf[type]['display']}
        self.assertEqual(output_obj, filtered_obj)

    def createGroup(self, name):
        dn = 'cn=%s,cn=groups,cn=accounts,dc=demo1,dc=freeipa,dc=org' % name
        self.lom.createObj(dn,
                           {'objectClass': ['posixgroup', 'nestedGroup'],
                            'gidNumber'  : ['1234567890']})
        return dn

    def removeGroup(self, name):
        dn = 'cn=%s,cn=groups,cn=accounts,dc=demo1,dc=freeipa,dc=org' % name
        self.lom.deleteObj(dn)

    def verifyGroupContainsUser(self, group_dn, user_name):
        group = self.lom.getSingle(group_dn, 'objectClass=*')
        user_dn = self.lom.getSingle(conf['user']['base'],
                                     '%s=%s' %(conf['user']['identifier'],
                                               user_name)
                                    )[0]
        self.assertIn(user_dn, group[1].get('member', []))

    def verifyGroupDoesNotContainUser(self, group_dn, user_name):
        group = self.lom.getSingle(group_dn, 'objectClass=*')
        user_dn = self.lom.getSingle(conf['user']['base'],
                                     '%s=%s' %(conf['user']['identifier'],
                                               user_name)
                                    )[0]
        self.assertNotIn(user_dn, group[1].get('member', []))

class LdapadmBasicTests(LdapadmTest):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        self.assertLdapadmFails(use_default_config=False)

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(runLdapadm("-h")[0], r'usage:')
        self.assertRegexpMatches(runLdapadm("--help")[0], r'usage:')

class LdapadmGetTests(LdapadmTest):

    def getOutput(self, type, search_term):
        return runLdapadm('get', type, search_term)

    def getObject(self, type, search_term):
        return self.lom.getSingle(conf[type]['base'],
            '%s=%s' %(conf[type]['identifier'], search_term))

    def verifyCanGet(self, type, search_term):
        output = self.getOutput(type, search_term)
        object = self.getObject(type, search_term)
        self.verifyOutput(output, object, type, search_term)

    def verifyCannotGet(self, type, search_term):
        self.assertLdapadmFails('get', type, search_term)

    def testGetWithBadArgumentsReturnsError(self):
        self.assertLdapadmFails('get')
        self.assertLdapadmFails('get', 'bogus')

    def testSimpleGetUser(self):

        for user in ('bogus', 'totallynotauser'):
            self.verifyCannotGet('user', user)
        for user in ('admin', 'manager', 'employee', 'helpdesk'):
            self.verifyCanGet('user', user)

    def testMultipleGetUser(self):
        pass

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

class LdapadmSearchTests(LdapadmTest):

    def testSearchUser(self):
        output = yaml.load(runLdapadm('search', 'user', 'Test')[0])
        expected_cns = [
            'Test Employee',
            'Test Helpdesk',
            'Test Manager']
        cns = [r[1]['cn'][0] for r in output['Test']]
        self.assertItemsEqual(cns, expected_cns)

class LdapadmInsertTests(LdapadmTest):

    def setUp(self):
        # create group object with blank member attribute
        self.obj_cn = 'foobars'
        super(LdapadmInsertTests, self).setUp()
        self.obj_dn = self.createGroup(self.obj_cn)

    def verifyGroupContainsUser(self, group_dn, user_name):
        group = self.lom.getSingle(group_dn, 'objectClass=*')
        user_dn = self.lom.getSingle(conf['user']['base'],
                                     '%s=%s' %(conf['user']['identifier'],
                                               user_name)
                                    )[0]
        self.assertIn(user_dn, group[1]['member'])

    def testInsertWithBadArgumentsReturnsError(self):
        self.assertLdapadmFails('insert')
        self.assertLdapadmFails('insert', 'boguscommand')
        self.assertLdapadmFails('insert', 'group', 'bogusgroup')
        self.assertLdapadmFails('insert', 'access', 'bogusgroup')

    def testInsertGroupCanInsertSingleUser(self):
        for user in ['helpdesk', 'employee', 'manager']:
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)
            runLdapadm('insert', 'group', self.obj_cn, user)
            self.verifyGroupContainsUser(self.obj_dn, user)

    def testInsertAccessCanInsertSingleUser(self):
        for user in ['helpdesk', 'employee', 'manager']:
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)
            runLdapadm('insert', 'access', self.obj_cn, user)
            self.verifyGroupContainsUser(self.obj_dn, user)

    def testInsertCanInsertMultipleUsers(self):
        users = ['helpdesk', 'employee', 'manager']
        for user in users:
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)
        runLdapadm('insert', 'group', self.obj_cn,
                   'employee', 'manager', 'helpdesk')
        for user in users:
            self.verifyGroupContainsUser(self.obj_dn, user)

    def tearDown(self):
        # remove group object
        self.removeGroup(self.obj_cn)

class LdapadmRemoveTests(LdapadmTest):

    def setUp(self):
        super(LdapadmRemoveTests, self).setUp()
        self.obj_cn = 'bazbars'
        self.obj_dn = self.createGroup(self.obj_cn)
        self.users = ['helpdesk', 'employee', 'manager']
        for u in self.users:
            dn = self.lom.getSingle(conf['user']['base'],
                "%s=%s" %(conf['user']['identifier'], u))[0]
            self.lom.addAttr(conf['group']['base'],
                self.obj_dn, 
                'member',
                dn)

    def testRemoveGroupCanRemoveSingleUser(self):
        for user in self.users:
            self.verifyGroupContainsUser(self.obj_dn, user)
            runLdapadm('remove', 'group', self.obj_cn, user)
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)

    def testRemoveAccessCanRemoveSingleUser(self):
        for user in ['helpdesk', 'employee', 'manager']:
            self.verifyGroupContainsUser(self.obj_dn, user)
            runLdapadm('remove', 'access', self.obj_cn, user)
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)

    def testRemoveCanRemoveMultipleUsers(self):
        users = ['helpdesk', 'employee', 'manager']
        for user in users:
            self.verifyGroupContainsUser(self.obj_dn, user)
        runLdapadm('remove', 'group', self.obj_cn,
                   'employee', 'manager', 'helpdesk')
        for user in users:
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)

    def tearDown(self):
        # remove group object
        self.removeGroup(self.obj_cn)
