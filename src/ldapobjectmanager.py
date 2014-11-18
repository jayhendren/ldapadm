import ldap

class auth():
    kerb, simple, noauth = range(3)

class LDAPObjectManager():

    def __init__(self, uri, authtype, **kwargs):
        self.ldo = ldap.initialize(uri)

    def _stripReferences(self, ldif):
        return filter(lambda x: x[0] is not None, ldif)

    def gets(self, sbase, sfilter):
        ldif = self.ldo.search_ext_s(sbase, ldap.SCOPE_SUBTREE, sfilter)
        result = self._stripReferences(ldif)
        if not result:
            raise RuntimeError("No results found for single-object query: \
base %s filter: %s" %(sbase, sfilter))
        if len(result) > 1:
            raise RuntimeError("Too many results found for single-object \
query: base: %s filter: %s results: %s" %(sbase, sfilter, \
                [r[0] for r in result]))
        return result[0]
