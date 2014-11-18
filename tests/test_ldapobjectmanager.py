import mock
import unittest
import src.ldapobjectmanager

@mock.patch('src.ldapobjectmanager.ldap', autospec=True)
class TestLOMGetMethods(unittest.TestCase):

    def setUp(self):
        self.uri = 'ldaps://foo.bar:636'
        self.lom = src.ldapobjectmanager.LDAPObjectManager(self.uri,
            src.ldapobjectmanager.auth.kerb)

    # tests for LOM.gets()
    
    def testGetsEmptyException(self, mock_ldap):
        ldo = mock_ldap.ldapobject.LDAPObject(self.uri)
        mock_ldap.initialize.return_value = ldo

        # if gets() fails to find an object, it should throw an exception
        ldo.search_ext_s.return_value = []
        with self.assertRaises(RuntimeError) as err:
            self.lom.gets("", "")
