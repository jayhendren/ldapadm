import os
import subprocess
import yaml
import unittest
import ldap
from src.ldapadm import LDAPObjectManager, auth

proj_root_dir = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
conf_path = os.path.join(proj_root_dir, 'tests/ldapadm-test.conf.yaml')

class LdapadmTest(unittest.TestCase):

    def setUp(self):
        self.conf = yaml.load(file(conf_path, 'r'))
        self.lom = self.getLOM()

    def getLOM(self):
        return LDAPObjectManager(self.conf['uri'], auth.simple,
                                 user=self.conf['username'],
                                 password=self.conf['password'])

    def runLdapadm(self, *args, **kwargs):
        # runLdapadm() returns tuple (stdout, stderr, exitcode)
    
        use_default_config = kwargs.get('use_default_config', True)
    
        if use_default_config:
            args = ('-c', conf_path) + args
    
        cmd = [os.path.join(proj_root_dir, 'src/ldapadm.py')] + list(args)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        result = proc.communicate()
        result = result + (proc.returncode,)
    
        return result

    def assertLdapadmSucceeds(self, *args, **kwargs):
        self.assertEqual(self.runLdapadm(*args, **kwargs)[2], 0)

    def assertLdapadmFails(self, *args, **kwargs):
        self.assertNotEqual(self.runLdapadm(*args, **kwargs)[2], 0)

    def verifyOutput(self, output, object, type, search_term):
        output_obj = yaml.load(output[0])[search_term]['results'][0][1]
        filtered_obj = {k:object[1].get(k) \
                        for k in self.conf[type]['display']}
        self.assertEqual(output_obj, filtered_obj)

    def createGroup(self, name):
        dn = 'cn=%s,cn=groups,cn=accounts,dc=demo1,dc=freeipa,dc=org' % name
        self.lom.create_object(dn,
                           {'objectClass': ['posixgroup', 'nestedGroup'],
                            'gidNumber'  : ['1234567890']})
        return dn

    def removeGroup(self, name):
        dn = 'cn=%s,cn=groups,cn=accounts,dc=demo1,dc=freeipa,dc=org' % name
        self.lom.delete_object(dn)

    def verifyGroupContainsUser(self, group_dn, user_name):
        group = self.lom.get_single(group_dn, 'objectClass=*')
        user_dn = self.lom.get_single(self.conf['user']['base'],
                                     '%s=%s' %(self.conf['user']['identifier'],
                                               user_name)
                                    )[0]
        self.assertIn(user_dn, group[1].get('member', []))

    def verifyGroupDoesNotContainUser(self, group_dn, user_name):
        group = self.lom.get_single(group_dn, 'objectClass=*')
        user_dn = self.lom.get_single(self.conf['user']['base'],
                                     '%s=%s' %(self.conf['user']['identifier'],
                                               user_name)
                                    )[0]
        self.assertNotIn(user_dn, group[1].get('member', []))

    def verifyDoesExist(self, dn):
        self.assertEqual(self.lom.get_single(dn, 'objectClass=*')[0], dn)

    def verifyDoesNotExist(self, dn):
        self.assertRaises(ldap.NO_SUCH_OBJECT,
                          self.lom.get_multiple,
                          dn, 
                          'objectClass=*')

class LdapadmBasicTests(LdapadmTest):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        self.assertLdapadmFails(use_default_config=False)

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(self.runLdapadm("-h")[0], r'usage:')
        self.assertRegexpMatches(self.runLdapadm("--help")[0], r'usage:')

class LdapadmGetTests(LdapadmTest):

    def getOutput(self, type, search_term):
        return self.runLdapadm('get', type, search_term)

    def getObject(self, type, search_term):
        return self.lom.get_single(self.conf[type]['base'],
            '%s=%s' %(self.conf[type]['identifier'], search_term))

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
        output = yaml.load(self.runLdapadm('search', 'user', 'Test')[0])
        expected_cns = [
            'Test Employee',
            'Test Helpdesk',
            'Test Manager']
        cns = [r[1]['cn'][0] for r in output['Test']['results']]
        self.assertItemsEqual(cns, expected_cns)

class LdapadmCreateAndRemoveTests(LdapadmTest):

    def testCreateAndRemove(self):
        # Yes, I'm lazy...
        name = 'ldapadmtest'
        self.verifyDoesNotExist('%s=%s,%s' %(self.conf['user']['identifier'],
                                             name,
                                             self.conf['user']['base']))
        options = 'user: {schema: {cn: [yellow], sn:[blue], ' +\
                  'uidNumber: ["98765"], gidNumber: ["98765"],' +\
                  'homedirectory: ["/home/red"]}}'
        self.runLdapadm('-o', options, 'create', 'user', name)
        self.verifyDoesExist('%s=%s,%s' %(self.conf['user']['identifier'],
                                          name,
                                          self.conf['user']['base']))
        self.runLdapadm('delete', 'user', name)
        self.verifyDoesNotExist('%s=%s,%s' %(self.conf['user']['identifier'],
                                             name,
                                             self.conf['user']['base']))

class LdapadmInsertTests(LdapadmTest):

    def setUp(self):
        # create group object with blank member attribute
        self.obj_cn = 'foobars'
        super(LdapadmInsertTests, self).setUp()
        self.obj_dn = self.createGroup(self.obj_cn)

    def verifyGroupContainsUser(self, group_dn, user_name):
        group = self.lom.get_single(group_dn, 'objectClass=*')
        user_dn = self.lom.get_single(self.conf['user']['base'],
                                     '%s=%s' %(self.conf['user']['identifier'],
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
            self.runLdapadm('insert', 'group', self.obj_cn, 'user', user)
            self.verifyGroupContainsUser(self.obj_dn, user)

    def testInsertAccessCanInsertSingleUser(self):
        for user in ['helpdesk', 'employee', 'manager']:
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)
            self.runLdapadm('insert', 'access', self.obj_cn, 'user', user)
            self.verifyGroupContainsUser(self.obj_dn, user)

    def testInsertCanInsertMultipleUsers(self):
        users = ['helpdesk', 'employee', 'manager']
        for user in users:
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)
        self.runLdapadm('insert', 'group', self.obj_cn, 'user',
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
            dn = self.lom.get_single(self.conf['user']['base'],
                "%s=%s" %(self.conf['user']['identifier'], u))[0]
            self.lom.add_attribute(self.conf['group']['base'],
                self.obj_dn, 
                'member',
                dn)

    def testRemoveGroupCanRemoveSingleUser(self):
        for user in self.users:
            self.verifyGroupContainsUser(self.obj_dn, user)
            self.runLdapadm('remove', 'group', self.obj_cn, 'user', user)
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)

    def testRemoveAccessCanRemoveSingleUser(self):
        for user in ['helpdesk', 'employee', 'manager']:
            self.verifyGroupContainsUser(self.obj_dn, user)
            self.runLdapadm('remove', 'access', self.obj_cn, 'user', user)
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)

    def testRemoveCanRemoveMultipleUsers(self):
        users = ['helpdesk', 'employee', 'manager']
        for user in users:
            self.verifyGroupContainsUser(self.obj_dn, user)
        self.runLdapadm('remove', 'group', self.obj_cn, 'user',
                   'employee', 'manager', 'helpdesk')
        for user in users:
            self.verifyGroupDoesNotContainUser(self.obj_dn, user)

    def tearDown(self):
        # remove group object
        self.removeGroup(self.obj_cn)
