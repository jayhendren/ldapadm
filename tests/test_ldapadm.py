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
        'base': base,
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

class LdapadmOutput():

    def __init__(self, *args, **kwargs):
        use_default_config = kwargs.get('use_default_config', True)
    
        if use_default_config:
            args = ('-c', conf_path) + args
    
        cmd = [os.path.join(proj_root_dir, 'src/ldapadm.py')] + list(args)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        self.stdout, self.stderr = proc.communicate()
        try:
            self.output_object = yaml.load(self.stdout)
        except yaml.scanner.ScannerError:
            self.output_object = None
        self.code = proc.returncode
        self.success = (self.code == 0) and self.output_object and \
            all([v['success'] for k, v in self.output_object.items()])

    def containsObject(self, object):
        dns = list((r[0] for k, v in self.output_object.items() \
                         for r in v.get('results')))
        dn = object[0]
        return dn in dns

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

    def getDN(self, type, name):
        return "cn=%s,%s" %(name, config[type]['base'])

    def getNewTestObjectAttributes(self, type):
        return {'objectClass': ['test%s' %type], 'testAttribute': 'test me'}

    def getNewTestObjectModlist(self, type):
        return ldap.modlist.addModlist(self.getNewTestObjectAttributes(type))

    def getObjectByDN(self, dn):
        return ldapobject.search_ext_s(dn, ldap.SCOPE_BASE)[0]

    def getObjectByName(self, type, name):
        return self.getObjectByDN(self.getDN(type, name))

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
        user_object = self.getObjectByDN(user_dn)[1]

        # add user to members list
        new_group_object = copy.deepcopy(group_object)
        member_list = new_group_object.get('member', [])
        member_list.append(user_dn)
        new_group_object['member'] = member_list
        modlist = ldap.modlist.modifyModlist(group_object, new_group_object)
        ldapobject.modify_ext_s(group_dn, modlist)

        # add group to memberOf list
        new_user_object = copy.deepcopy(user_object)
        member_of_list = new_user_object.get('memberOf', [])
        member_of_list.append(group_dn)
        new_user_object['memberOf'] = member_of_list
        modlist = ldap.modlist.modifyModlist(user_object, new_user_object)
        ldapobject.modify_ext_s(user_dn, modlist)

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

    def verifyOutputContains(self, output, type, name):
        object = self.getObjectByName(type, name)
        self.assertTrue(output.containsObject(object))

    def verifyOutputDoesNotContain(self, output, type, name):
        object = self.getObjectByName(type, name)
        self.assertFalse(output.containsObject(object))

    def ldapadmGet(self, type, name):
        return LdapadmOutput('get', type, name)

    def ldapadmSearch(self, type, search_term):
        return LdapadmOutput('search', type, search_term)

    def ldapadmCreateObject(self, type, name):
        options = yaml.dump({type: {'schema': \
                            self.getNewTestObjectAttributes(type)}})
        return LdapadmOutput('-o', options, 'create', type, name)

    def ldapadmDeleteObject(self, type, name):
        return LdapadmOutput('delete', type, name)

    def ldapadmInsert(self, group, user):
        return LdapadmOutput('insert', 'group', group, 'user', user)

    def ldapadmRemove(self, group, user):
        return LdapadmOutput('remove', 'group', group, 'user', user)

    def ldapadmMembers(self, group):
        return LdapadmOutput('members', 'group', group)

    def ldapadmMembership(self, user):
        return LdapadmOutput('membership', 'user', user)

class LdapadmBasicTests(LdapadmTest):

    def testLdapadmCalledWithoutArgumentsReturnsError(self):
        self.assertFalse(LdapadmOutput(use_default_config=False).success)

    def testHelpSwitchesExitCodeZeroAndProduceOutput(self):
        self.assertRegexpMatches(LdapadmOutput("-h").stdout, r'usage:')
        self.assertRegexpMatches(LdapadmOutput("--help").stdout, r'usage:')

class LdapadmGetTests(LdapadmTest):

    def testSingleGetUser(self):
        user1, user2 = random.sample(self.user_list, 2)
        output = self.ldapadmGet('user', user1)
        self.verifyOutputContains(output, 'user', user1)
        self.verifyOutputDoesNotContain(output, 'user', user2)

    def testSingleGetGroup(self):
        group1, group2 = random.sample(self.group_list, 2)
        output = self.ldapadmGet('group', group1)
        self.verifyOutputContains(output, 'group', group1)
        self.verifyOutputDoesNotContain(output, 'group', group2)

class LdapadmSearchTests(LdapadmTest):

    def testSearchUser(self):
        search_term = 'test me'
        output = self.ldapadmSearch('user', search_term)
        for user in self.user_list:
            self.verifyOutputContains(output, 'user', user)

class LdapadmCreateTests(LdapadmTest):

    def testCreateUser(self):
        name = 'foobar'
        object_type = 'user'
        self.verifyObjectDoesNotExistByName(object_type, name)
        output = self.ldapadmCreateObject(object_type, name)
        self.verifyObjectExistsByName(object_type, name)
        self.verifyOutputContains(output, object_type, name)

class LdapadmDeleteTests(LdapadmTest):

    def testDeleteUser(self):
        object_type = 'user'
        user = random.choice(self.user_list)
        self.verifyObjectExistsByName(object_type, user)
        self.ldapadmDeleteObject(object_type, user)
        self.verifyObjectDoesNotExistByName(object_type, user)

class LdapadmInsertTests(LdapadmTest):

    def testInsertWithBadArgumentsReturnsError(self):
        self.assertFalse(LdapadmOutput('insert').success)
        self.assertFalse(LdapadmOutput('insert', 'boguscommand').success)
        self.assertFalse(LdapadmOutput('insert', 'group', 'bogustype').success)

    def testInsertUserIntoGroup(self):
        group = random.choice(self.group_list)
        user = random.choice(self.user_list)
        self.verifyGroupDoesNotContainUser(group, user)
        self.ldapadmInsert(group, user)
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
        self.ldapadmRemove(group, user)
        self.verifyGroupDoesNotContainUser(group, user)

class LdapadmMemberTests(LdapadmTest):

    def testMembers(self):
        member, non_member = random.sample(self.user_list, 2)
        group = random.choice(self.group_list)
        self.insertUserIntoGroup(group, member)
        self.verifyGroupContainsUser(group, member)
        output = self.ldapadmMembers(group)
        self.verifyOutputContains(output, 'user', member)
        self.verifyOutputDoesNotContain(output, 'user', non_member)

class LdapadmMembershipTests(LdapadmTest):

    def testMembership(self):
        group, non_group = random.sample(self.group_list, 2)
        user = random.choice(self.user_list)
        self.insertUserIntoGroup(group, user)
        self.verifyGroupContainsUser(group, user)
        output = self.ldapadmMembership(user)
        self.verifyOutputContains(output, 'group', group)
        self.verifyOutputDoesNotContain(output, 'group', non_group)
