import ldap
import ldap.sasl

SCOPE=ldap.SCOPE_SUBTREE

class auth():
    kerb, simple, noauth = range(3)

class LDAPObjectManager():

    def __init__(self, uri, authtype, user=None, password=None, **kwargs):
        self._ldo = ldap.initialize(uri)
        for key, value in kwargs.items():
            self._ldo.set_option(getattr(ldap, key), value)
        if authtype == auth.simple:
            self._ldo.simple_bind_s(user, password)
        elif authtype == auth.kerb:
            self._ldo.sasl_interactive_bind_s('', ldap.sasl.gssapi())

    def _stripReferences(self, ldif):
        return filter(lambda x: x[0] is not None, ldif)

    def gets(self, sbase, sfilter):
        ldif = self._ldo.search_ext_s(sbase, SCOPE, sfilter)
        result = self._stripReferences(ldif)
        if not result:
            raise RuntimeError("""No results found for single-object query:
base: %s 
filter: %s""" %(sbase, sfilter))
        if len(result) > 1:
            raise RuntimeError("""Too many results found for single-object \
query:
base: %s
filter: %s
results: %s""" %(sbase, sfilter, [r[0] for r in result]))
        return result[0]

    def getm(self, sbase, sfilter):
        ldif = self._ldo.search_ext_s(sbase, SCOPE, sfilter)
        result = self._stripReferences(ldif)
        return result
