import mock
import unittest
import src.ldapobjectmanager
from src.ldapobjectmanager import LDAPObjectManager, auth

uri = 'ldaps://foo.bar:636'

def person(name):
    return ('CN={},OU=People,DC=foo,DC=bar'.format(name), {'name': [name]})

def reference():
    return (None, ['ldaps://foo.bar/cn=ref'])

class LOMTestCase(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch('src.ldapobjectmanager.ldap', autospec=True)
        self.mock_ldap = patcher.start()
        self.addCleanup(patcher.stop)

    def getNewLDOandLOM(self, auth, **kwargs):
        ldo = self.mock_ldap.ldapobject.LDAPObject(uri)
        self.mock_ldap.initialize.return_value = ldo
        lom = LDAPObjectManager(uri, auth, **kwargs)
        return ldo, lom

    def assert_no_calls(self, method):
        self.assertEqual(method.call_args_list, [])

class TestLOMInitializationAndOptions(LOMTestCase):

    def testNoAuth(self):
        ldo, lom = self.getNewLDOandLOM(auth.noauth)
        self.assert_no_calls(ldo.simple_bind_s)
        self.assert_no_calls(ldo.sasl_interactive_bind_s)

    def testSimpleAuth(self):
        user = 'foo'
        password = 'bar'
        ldo, lom = self.getNewLDOandLOM(auth.simple, user=user, password=password)
        ldo.simple_bind_s.assert_called_once_with(user, password)

    def testKerbAuth(self):
        sasl = mock.MagicMock()
        self.mock_ldap.sasl.gssapi.return_value = sasl
        ldo, lom = self.getNewLDOandLOM(auth.kerb)
        ldo.sasl_interactive_bind_s.assert_called_once_with('', sasl)

    def testAddInvalidOptionThrowsException(self):
        with self.assertRaises(AttributeError):
            ldo, lom = self.getNewLDOandLOM(auth.kerb, OPT_BOGUS=1)

    def testOptionKwargsAreSetOnConnectionObject(self):
        def assertOptionsAdded(**kwargs):
            ldo, lom = self.getNewLDOandLOM(auth.noauth, **kwargs)
            for key, value in kwargs.items():
                ldo.set_option.assert_any_call(getattr(self.mock_ldap, key),
                                               value)

        assertOptionsAdded(OPT_X_TLS=1)
        assertOptionsAdded(OPT_REFERRALS=0, OPT_URI="ldaps://baz.bar")

class LOMGetMethodsTestCase(LOMTestCase):

    def setUp(self):
        super(LOMGetMethodsTestCase, self).setUp()
        self.ldo, self.lom = self.getNewLDOandLOM(auth.kerb)

class TestLOMGets(LOMGetMethodsTestCase):

    def testGetsThrowsExceptionForNoResultsFound(self):
        self.ldo.search_ext_s.return_value = []
        with self.assertRaises(RuntimeError):
            self.lom.gets("", "")

    def testGetsThrowsExceptionForOnlyReferencesFound(self):
        # sometimes references are included in the result
        # these have no DN and should be discarded from the result
        self.ldo.search_ext_s.return_value = [(None, ['ldaps://foo.bar/cn=ref'])]
        with self.assertRaises(RuntimeError):
            self.lom.gets("", "")

    def testGetsSuccessfullyReturnsExactlyOneObject(self):
        alice = person('alice')
        self.ldo.search_ext_s.return_value = [alice]
        self.assertEqual(alice, self.lom.gets("", "name=alice"))

    def testGetsSuccessfullyReturnsExactlyOneObject(self):
        bob = person('bob')
        self.ldo.search_ext_s.return_value = [bob, reference()]
        self.assertEqual(bob, self.lom.gets("", "name=bob"))

    def testGetsThrowsExceptionWhenMultipleResultsFound(self):
        expectedresult = [person('fred'), person('george')]
        self.ldo.search_ext_s.return_value = expectedresult
        with self.assertRaises(RuntimeError):
            self.lom.gets("", "")

        self.assertEqual(expectedresult, self.lom.getm("", ""))

class TestLOMGetm(LOMGetMethodsTestCase):

    def testGetmSuccessfullyReturnsMultipleResults(self):
        expectedresult = [person('fred'), person('george')]
        self.ldo.search_ext_s.return_value = expectedresult
        self.assertEqual(expectedresult, self.lom.getm("", ""))

    def testGetmRemovesReferenceFromResult(self):
        susie = person('susie')
        ref = reference()
        self.ldo.search_ext_s.return_value = [
            ref, susie, susie, ref,
            ref, susie, susie, ref, susie, ref
        ]
        actualresult = self.lom.getm("", "name=susie")
        self.assertEqual([susie] * 5, actualresult)
