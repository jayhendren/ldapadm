import os
import subprocess
import yaml
import unittest
import ldap, ldap.modlist
import ldap_test
import random
import copy

proj_root_dir = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]
conf_path = os.path.join(proj_root_dir, 'tmp/ldapadm-test.conf.yaml')

def setUpModule():
    global server, config, ldapobject

    server = ldap_test.LdapServer()
    server.start()

    # create LDAP connection
    uri = 'ldap://localhost:%s' % server.config['port']
    base = server.config['base']['dn']
    ldapobject = ldap.initialize(uri)
    ldapobject.simple_bind_s(server.config['bind_dn'],
                             server.config['password'])

    # create group and user OUs
    user_base = "ou=testusers,%s" % base
    ldapobject.add_ext_s(user_base, ldap.modlist.addModlist({}))
    group_base = "ou=testgroups,%s" % base
    ldapobject.add_ext_s(group_base, ldap.modlist.addModlist({}))
    config = {
        'uri': uri,
        'user': {
            'base': user_base,
            'identifier': 'cn',
            'display': ['cn'],
            'search': ['cn', 'testAttribute']
            },
        'group': {
            'base': group_base,
            'identifier': 'cn',
            'display': ['cn'],
            'search': ['cn', 'testAttribute']
            }
        }
    tmpdir = os.path.dirname(conf_path)
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir)
    f = open(conf_path, 'w')
    f.write(yaml.dump(config))

def tearDownModule():
    global server
    server.stop()
    os.remove(conf_path)

class LdapadmTest(unittest.TestCase):

    def setUp(self):
        self.user_list = ('alice', 'bob', 'carol')
        self.group_list = ('athletes', 'nerds')
        for u in self.user_list: self.createObject('user', u)
        for g in self.group_list: self.createObject('group', g)

    def tearDown(self):
        # delete all test users and groups, not just those created in setUp()
        for o in ldapobject.search_ext_s(server.config['base']['dn'],
                ldap.SCOPE_SUBTREE,
                '(|(objectClass=testuser)(objectClass=testgroup))'):
            self.deleteObjectByDN(o[0])

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
        stdout, stderr, code = self.runLdapadm(*args, **kwargs)
        self.assertEqual(code, 0)
        output_obj = yaml.load(stdout)
        success = all([v['success'] for k, v in output_obj.items()])
        self.assertTrue(success)

    def assertLdapadmFails(self, *args, **kwargs):
        stdout, stderr, code = self.runLdapadm(*args, **kwargs)
        self.assertNotEqual(code, 0)
        output_obj = yaml.load(stdout)
        try:
            failure = not all([v['success'] for k, v in output_obj.items()])
        except AttributeError:
            self.assertTrue(False, "Expected YAML output.  Instead received:" +
                            "\nstdout:\n%s\n" %stdout +
                            "stderr:\n%s\n" %stderr +
                            "code:%s" %code)
        self.assertTrue(failure)

    def assertLdapadmFailsWithoutOutput(self, *args, **kwargs):
        stdout, stderr, code = self.runLdapadm(*args, **kwargs)
        self.assertNotEqual(code, 0)
        output_obj = yaml.load(stdout)
        self.assertIsNone(output_obj)

    def getDN(self, type, name):
        return "cn=%s,%s" %(name, config[type]['base'])

    def getNewTestObjectAttributes(self, type):
        return {'objectClass': ['test%s' %type], 'testAttribute': 'test me'}

    def getNewTestObjectModlist(self, type):
        return ldap.modlist.addModlist(self.getNewTestObjectAttributes(type))

    def getObjectByDN(self, dn):
        return ldapobject.search_ext_s(dn, ldap.SCOPE_BASE)[0]

    def createObject(self, type, name):
        dn = self.getDN(type, name)
        ldapobject.add_ext_s(dn, self.getNewTestObjectModlist(type))

    def deleteObject(self, type, name):
        dn = self.getDN(type, name)
        self.deleteObjectByDN(self, dn)

    def deleteObjectByDN(self, dn):
        ldapobject.delete_ext_s(dn)

    def insertUserIntoGroup(self, group, user):
        user_dn = self.getDN('user', user)
        group_dn = self.getDN('group', group)
        group_object = self.getObjectByDN(group_dn)[1]
        new_group_object = copy.deepcopy(group_object)
        member_list = new_group_object.get('member', [])
        member_list.append(user_dn)
        new_group_object['member'] = member_list
        modlist = ldap.modlist.modifyModlist(group_object, new_group_object)
        ldapobject.modify_ext_s(group_dn, modlist)

    def verifyOutput(self, output, object, type, search_term):
        try:
            output_obj = yaml.load(output[0])[search_term]['results'][0][1]
            filtered_obj = {k:object[1].get(k) \
                            for k in config[type]['display']}
            self.assertEqual(output_obj, filtered_obj)
        except IndexError:
            self.assertFalse(True, "unexpected output:\n" + output[0])

    def verifyDoesExistByDN(self, dn):
        self.assertEqual(self.getObjectByDN(dn)[0], dn)

    def verifyDoesNotExistByDN(self, dn):
        self.assertRaises(ldap.NO_SUCH_OBJECT, self.getObjectByDN, dn)

    def verifyObjectDoesNotExistByName(self, type, name):
        dn = self.getDN(type, name)
        self.verifyDoesNotExistByDN(dn)

    def verifyObjectExistsByName(self, type, name):
        dn = self.getDN(type, name)
        self.verifyDoesExistByDN(dn)

    def verifyGroupDoesNotContainUser(self, group, user):
        # this method doesn't work for nested groups (yet)
        group_dn = self.getDN('group', group)
        group_object = self.getObjectByDN(group_dn)
        user_dn = self.getDN('user', user)
        self.assertNotIn(user_dn, group_object[1].get('member', []))

    def verifyGroupContainsUser(self, group, user):
        # this method doesn't work for nested groups (yet)
        group_dn = self.getDN('group', group)
        group_object = self.getObjectByDN(group_dn)
        user_dn = self.getDN('user', user)
        self.assertIn(user_dn, group_object[1].get('member', []))

    def LdapadmCreateObject(self, type, name):
        options = yaml.dump({type: {'schema': \
                            self.getNewTestObjectAttributes(type)}})
        self.runLdapadm('-o', options, 'create', type, name)

    def LdapadmDeleteObject(self, type, name):
        self.runLdapadm('delete', type, name)

    def LdapadmInsert(self, group, user):
        self.runLdapadm('insert', 'group', group, 'user', user)

    def LdapadmRemove(self, group, user):
        self.runLdapadm('remove', 'group', group, 'user', user)

class LdapadmBasicTests(LdapadmTest):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        self.assertLdapadmFailsWithoutOutput(use_default_config=False)

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(self.runLdapadm("-h")[0], r'usage:')
        self.assertRegexpMatches(self.runLdapadm("--help")[0], r'usage:')

class LdapadmGetTests(LdapadmTest):

    def getOutput(self, type, search_term):
        return self.runLdapadm('get', type, search_term)

    def getObject(self, type, search_term):
        dn = self.getDN(type, search_term)
        return ldapobject.search_ext_s(dn, ldap.SCOPE_BASE)[0]

    def verifyCanGet(self, type, search_term):
        output = self.getOutput(type, search_term)
        object = self.getObject(type, search_term)
        self.verifyOutput(output, object, type, search_term)

    def verifyCannotGet(self, type, search_term):
        self.assertLdapadmFails('get', type, search_term)

    def testGetWithBadArgumentsReturnsError(self):
        self.assertLdapadmFailsWithoutOutput('get')
        self.assertLdapadmFailsWithoutOutput('get', 'bogus')

    def testSimpleGetUser(self):

        for user in ('bogus', 'totallynotauser'):
            self.verifyCannotGet('user', user)
        for user in self.user_list:
            self.verifyCanGet('user', user)
        for group in ('bogus', 'totallynotagroup'):
            self.verifyCannotGet('group', group)
        for group in self.group_list:
            self.verifyCanGet('group', group)

    def testMultipleGetUser(self):
        pass

class LdapadmSearchTests(LdapadmTest):

    def testSearchUser(self):
        search_term = 'test me'
        output = yaml.load(self.runLdapadm('search', 'user', search_term)[0])
        cns = [r[1]['cn'][0] for r in output[search_term]['results']]
        self.assertItemsEqual(cns, self.user_list)

class LdapadmCreateTests(LdapadmTest):

    def testCreateUser(self):
        name = 'foobar'
        object_type = 'user'
        self.verifyObjectDoesNotExistByName(object_type, name)
        self.LdapadmCreateObject(object_type, name)
        self.verifyObjectExistsByName(object_type, name)

class LdapadmDeleteTests(LdapadmTest):

    def testDeleteUser(self):
        object_type = 'user'
        for user in self.user_list:
            self.verifyObjectExistsByName(object_type, user)
            self.LdapadmDeleteObject(object_type, user)
            self.verifyObjectDoesNotExistByName(object_type, user)

class LdapadmInsertTests(LdapadmTest):

    def testInsertWithBadArgumentsReturnsError(self):
        self.assertLdapadmFailsWithoutOutput('insert')
        self.assertLdapadmFailsWithoutOutput('insert', 'boguscommand')
        self.assertLdapadmFailsWithoutOutput('insert', 'group', 'bogusgroup')

    def testInsertUserIntoGroup(self):
        group = random.choice(self.group_list)
        user = random.choice(self.user_list)
        self.verifyGroupDoesNotContainUser(group, user)
        self.LdapadmInsert(group, user)
        self.verifyGroupContainsUser(group, user)

class LdapadmRemoveTests(LdapadmTest):

    def setUp(self):
        super(LdapadmRemoveTests, self).setUp()
        # insert every user into every group
        for (group, user) in ((g, u) for g in self.group_list \
                                     for u in self.user_list):
            self.insertUserIntoGroup(group, user)

    def testRemoveGroupCanRemoveSingleUser(self):
        group = random.choice(self.group_list)
        user = random.choice(self.user_list)
        self.verifyGroupContainsUser(group, user)
        self.LdapadmRemove(group, user)
        self.verifyGroupDoesNotContainUser(group, user)
