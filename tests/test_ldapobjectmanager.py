import mock
import unittest
import src.ldapobjectmanager

@mock.patch('src.ldapobjectmanager.ldap', autospec=True)
class TestLOMGetMethods(unittest.TestCase):

    def setUp(self):
        pass

    def testAuth(self, mock_ldap):
        uri = 'ldaps://foo.bar:636'

        # no auth
        ldo = mock_ldap.ldapobject.LDAPObject(uri)
        mock_ldap.initialize.return_value = ldo
        lom = src.ldapobjectmanager.LDAPObjectManager(uri,
            src.ldapobjectmanager.auth.noauth)
        self.assertEqual(ldo.simple_bind_s.call_args_list, [])
        self.assertEqual(ldo.sasl_interactive_bind_s.call_args_list, [])

        # simple auth
        ldo = mock_ldap.ldapobject.LDAPObject(uri)
        mock_ldap.initialize.return_value = ldo
        user = 'foo'
        password = 'bar'
        lom = src.ldapobjectmanager.LDAPObjectManager(uri,
            src.ldapobjectmanager.auth.simple, user=user, password=password)
        self.assertEqual(ldo.simple_bind_s.call_args_list,
            [((user, password),)])

        # kerb auth
        ldo = mock_ldap.ldapobject.LDAPObject(uri)
        mock_ldap.initialize.return_value = ldo
        sasl = mock.MagicMock()
        mock_ldap.sasl.gssapi.return_value = sasl
        lom = src.ldapobjectmanager.LDAPObjectManager(uri,
            src.ldapobjectmanager.auth.kerb)
        self.assertEqual(ldo.sasl_interactive_bind_s.call_args_list,
            [(('', sasl),)])
    
    def testGets(self, mock_ldap):
        uri = 'ldaps://foo.bar:636'
        ldo = mock_ldap.ldapobject.LDAPObject(uri)
        mock_ldap.initialize.return_value = ldo
        lom = src.ldapobjectmanager.LDAPObjectManager(uri,
            src.ldapobjectmanager.auth.kerb)

        # if gets() fails to find an object, it should throw an exception
        ldo.search_ext_s.return_value = []
        with self.assertRaises(RuntimeError) as err:
            lom.gets("", "")

        # sometimes references are included in the result
        # these have no DN and should be discarded from the result
        ldo.search_ext_s.return_value = [(None, ['ldaps://foo.bar/cn=ref'])]
        with self.assertRaises(RuntimeError) as err:
            lom.gets("", "")

        # if gets() finds > 1 object, it should throw an exception
        ldo.search_ext_s.return_value = [
            ('CN=fred,OU=People,DC=foo,DC=bar', {'name': ['fred']}),
            ('CN=george,OU=People,DC=foo,DC=bar', {'name': ['george']})
            ]
        with self.assertRaises(RuntimeError) as err:
            lom.gets("", "(|(name=fred)(name=george))")

        # if gets() finds exactly 1 object, it should return that object
        expectedresult = ('CN=alice,OU=People,DC=foo,DC=bar', {'name': ['alice']})
        ldo.search_ext_s.return_value = [expectedresult]
        actualresult = lom.gets("", "name=alice")
        self.assertEqual(expectedresult, actualresult)

        # repeat with reference in result
        expectedresult = ('CN=alice,OU=People,DC=foo,DC=bar', {'name': ['alice']})
        ldo.search_ext_s.return_value = [expectedresult,
            (None, ['ldaps://foo.bar/cn=ref'])]
        actualresult = lom.gets("", "name=alice")
        self.assertEqual(expectedresult, actualresult)
