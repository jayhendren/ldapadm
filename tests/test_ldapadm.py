import os
import subprocess
import yaml
import unittest
import ldap, ldap.modlist
import ldap_test

proj_root_dir = os.path.split(os.path.dirname(os.path.realpath(__file__)))[0]

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
            'base': user_base
            },
        'group': {
            'base': group_base
            }
        }

def tearDownModule():
    global server
    server.stop()

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
            args = ('-o', yaml.dump(config)) + args
    
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
        failure = any([v['success'] for k, v in output_obj.items()])
        self.assertTrue(success)

    def assertLdapadmFailsWithoutOutput(self, *args, **kwargs):
        stdout, stderr, code = self.runLdapadm(*args, **kwargs)
        self.assertNotEqual(code, 0)
        output_obj = yaml.load(stdout)
        self.assertIsNone(output_obj)

    def verifyOutput(self, output, object, type, search_term):
        output_obj = yaml.load(output[0])[search_term]['results'][0][1]
        filtered_obj = {k:object[1].get(k) \
                        for k in self.conf[type]['display']}
        self.assertEqual(output_obj, filtered_obj)

    def getDN(self, type, name):
        return "cn=%s,%s" %(name, config[type]['base'])

    def createObject(self, type, name):
        dn = self.getDN(type, name)
        ldapobject.add_ext_s(dn, ldap.modlist.addModlist({'objectClass':
                                                          ['test%s' %type]}))

    def deleteObject(self, type, name):
        dn = self.getDN(type, name)
        self.deleteObjectByDN(self, dn)

    def deleteObjectByDN(self, dn):
        ldapobject.delete_ext_s(dn)

    # def createGroup(self, name):
    #     dn = 'cn=%s,cn=groups,cn=accounts,dc=demo1,dc=freeipa,dc=org' % name
    #     self.lom.create_object(dn,
    #                        {'objectClass': ['posixgroup', 'nestedGroup'],
    #                         'gidNumber'  : ['1234567890']})
    #     return dn

    # def deleteGroup(self, name):
    #     dn = 'cn=%s,cn=groups,cn=accounts,dc=demo1,dc=freeipa,dc=org' % name
    #     self.lom.delete_object(dn)

    # def verifyGroupContainsUser(self, group_dn, user_name):
    #     group = self.lom.get_single(group_dn, 'objectClass=*')
    #     user_dn = self.lom.get_single(self.conf['user']['base'],
    #                                  '%s=%s' %(self.conf['user']['identifier'],
    #                                            user_name)
    #                                 )[0]
    #     self.assertIn(user_dn, group[1].get('member', []))

    # def verifyGroupDoesNotContainUser(self, group_dn, user_name):
    #     group = self.lom.get_single(group_dn, 'objectClass=*')
    #     user_dn = self.lom.get_single(self.conf['user']['base'],
    #                                  '%s=%s' %(self.conf['user']['identifier'],
    #                                            user_name)
    #                                 )[0]
    #     self.assertNotIn(user_dn, group[1].get('member', []))

    # def verifyDoesExist(self, dn):
    #     self.assertEqual(self.lom.get_single(dn, 'objectClass=*')[0], dn)

    # def verifyDoesNotExist(self, dn):
    #     self.assertRaises(ldap.NO_SUCH_OBJECT,
    #                       self.lom.get_multiple,
    #                       dn, 
    #                       'objectClass=*')

class LdapadmBasicTests(LdapadmTest):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        self.assertLdapadmFailsWithoutOutput(use_default_config=False)

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(self.runLdapadm("-h")[0], r'usage:')
        self.assertRegexpMatches(self.runLdapadm("--help")[0], r'usage:')

# class LdapadmGetTests(LdapadmTest):
# 
#     def getOutput(self, type, search_term):
#         return self.runLdapadm('get', type, search_term)
# 
#     def getObject(self, type, search_term):
#         return self.lom.get_single(self.conf[type]['base'],
#             '%s=%s' %(self.conf[type]['identifier'], search_term))
# 
#     def verifyCanGet(self, type, search_term):
#         output = self.getOutput(type, search_term)
#         object = self.getObject(type, search_term)
#         self.verifyOutput(output, object, type, search_term)
# 
#     def verifyCannotGet(self, type, search_term):
#         self.assertLdapadmFails('get', type, search_term)
# 
#     def testGetWithBadArgumentsReturnsError(self):
#         self.assertLdapadmFails('get')
#         self.assertLdapadmFails('get', 'bogus')
# 
#     def testSimpleGetUser(self):
# 
#         for user in ('bogus', 'totallynotauser'):
#             self.verifyCannotGet('user', user)
#         for user in ('admin', 'manager', 'employee', 'helpdesk'):
#             self.verifyCanGet('user', user)
# 
#     def testMultipleGetUser(self):
#         pass
# 
#     def testSimpleGetUnixGroup(self):
# 
#         for group in ('bogus', 'totallynotagroup'):
#             self.verifyCannotGet('group', group)
#         for group in ('admins', 'managers', 'employees', 'helpdesk'):
#             self.verifyCanGet('group', group)
# 
#     def testSimpleGetAccessGroup(self):
# 
#         for access in ('bogus', 'totallynotaaccess'):
#             self.verifyCannotGet('access', access)
#         for access in ('admins', 'managers', 'employees', 'helpdesk'):
#             self.verifyCanGet('access', access)
# 
# class LdapadmSearchTests(LdapadmTest):
# 
#     def testSearchUser(self):
#         output = yaml.load(self.runLdapadm('search', 'user', 'Test')[0])
#         expected_cns = [
#             'Test Employee',
#             'Test Helpdesk',
#             'Test Manager']
#         cns = [r[1]['cn'][0] for r in output['Test']['results']]
#         self.assertItemsEqual(cns, expected_cns)
# 
# class LdapadmCreateAndRemoveTests(LdapadmTest):
# 
#     def testCreateAndRemove(self):
#         # Yes, I'm lazy...
#         name = 'ldapadmtest'
#         self.verifyDoesNotExist('%s=%s,%s' %(self.conf['user']['identifier'],
#                                              name,
#                                              self.conf['user']['base']))
#         options = 'user: {schema: {cn: [yellow], sn:[blue], ' +\
#                   'uidNumber: ["98765"], gidNumber: ["98765"],' +\
#                   'homedirectory: ["/home/red"]}}'
#         self.runLdapadm('-o', options, 'create', 'user', name)
#         self.verifyDoesExist('%s=%s,%s' %(self.conf['user']['identifier'],
#                                           name,
#                                           self.conf['user']['base']))
#         self.runLdapadm('delete', 'user', name)
#         self.verifyDoesNotExist('%s=%s,%s' %(self.conf['user']['identifier'],
#                                              name,
#                                              self.conf['user']['base']))
# 
# class LdapadmInsertTests(LdapadmTest):
# 
#     def setUp(self):
#         # create group object with blank member attribute
#         self.obj_cn = 'foobars'
#         super(LdapadmInsertTests, self).setUp()
#         self.obj_dn = self.createGroup(self.obj_cn)
# 
#     def verifyGroupContainsUser(self, group_dn, user_name):
#         group = self.lom.get_single(group_dn, 'objectClass=*')
#         user_dn = self.lom.get_single(self.conf['user']['base'],
#                                      '%s=%s' %(self.conf['user']['identifier'],
#                                                user_name)
#                                     )[0]
#         self.assertIn(user_dn, group[1]['member'])
# 
#     def testInsertWithBadArgumentsReturnsError(self):
#         self.assertLdapadmFails('insert')
#         self.assertLdapadmFails('insert', 'boguscommand')
#         self.assertLdapadmFails('insert', 'group', 'bogusgroup')
#         self.assertLdapadmFails('insert', 'access', 'bogusgroup')
# 
#     def testInsertGroupCanInsertSingleUser(self):
#         for user in ['helpdesk', 'employee', 'manager']:
#             self.verifyGroupDoesNotContainUser(self.obj_dn, user)
#             self.runLdapadm('insert', 'group', self.obj_cn, 'user', user)
#             self.verifyGroupContainsUser(self.obj_dn, user)
# 
#     def testInsertAccessCanInsertSingleUser(self):
#         for user in ['helpdesk', 'employee', 'manager']:
#             self.verifyGroupDoesNotContainUser(self.obj_dn, user)
#             self.runLdapadm('insert', 'access', self.obj_cn, 'user', user)
#             self.verifyGroupContainsUser(self.obj_dn, user)
# 
#     def testInsertCanInsertMultipleUsers(self):
#         users = ['helpdesk', 'employee', 'manager']
#         for user in users:
#             self.verifyGroupDoesNotContainUser(self.obj_dn, user)
#         self.runLdapadm('insert', 'group', self.obj_cn, 'user',
#                    'employee', 'manager', 'helpdesk')
#         for user in users:
#             self.verifyGroupContainsUser(self.obj_dn, user)
# 
#     def tearDown(self):
#         # remove group object
#         self.deleteGroup(self.obj_cn)
# 
# class LdapadmRemoveTests(LdapadmTest):
# 
#     def setUp(self):
#         super(LdapadmRemoveTests, self).setUp()
#         self.obj_cn = 'bazbars'
#         self.obj_dn = self.createGroup(self.obj_cn)
#         self.users = ['helpdesk', 'employee', 'manager']
#         for u in self.users:
#             dn = self.lom.get_single(self.conf['user']['base'],
#                 "%s=%s" %(self.conf['user']['identifier'], u))[0]
#             self.lom.add_attribute(self.conf['group']['base'],
#                 self.obj_dn, 
#                 'member',
#                 dn)
# 
#     def testRemoveGroupCanRemoveSingleUser(self):
#         for user in self.users:
#             self.verifyGroupContainsUser(self.obj_dn, user)
#             self.runLdapadm('remove', 'group', self.obj_cn, 'user', user)
#             self.verifyGroupDoesNotContainUser(self.obj_dn, user)
# 
#     def testRemoveAccessCanRemoveSingleUser(self):
#         for user in ['helpdesk', 'employee', 'manager']:
#             self.verifyGroupContainsUser(self.obj_dn, user)
#             self.runLdapadm('remove', 'access', self.obj_cn, 'user', user)
#             self.verifyGroupDoesNotContainUser(self.obj_dn, user)
# 
#     def testRemoveCanRemoveMultipleUsers(self):
#         users = ['helpdesk', 'employee', 'manager']
#         for user in users:
#             self.verifyGroupContainsUser(self.obj_dn, user)
#         self.runLdapadm('remove', 'group', self.obj_cn, 'user',
#                    'employee', 'manager', 'helpdesk')
#         for user in users:
#             self.verifyGroupDoesNotContainUser(self.obj_dn, user)
# 
#     def tearDown(self):
#         # remove group object
#         self.deleteGroup(self.obj_cn)
