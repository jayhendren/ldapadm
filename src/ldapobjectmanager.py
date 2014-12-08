import ldap
import ldap.sasl
import ldap.modlist
import textwrap
import copy

SCOPE=ldap.SCOPE_SUBTREE # hardcoded for now; to be moved to configuration

class auth():
    kerb, simple, noauth = "kerb_auth", "simple_auth", "no_auth"

class LDAPObjectManager():

    def __init__(self, uri, authtype, user=None, password=None, **kwargs):
        # not sure that I like hardcoding the list of supported auth types...
        if not authtype in [auth.kerb, auth.simple, auth.noauth]:
            raise ValueError("'%s' is not a supported authentication method" \
                             % authtype)
        self._ldo = ldap.initialize(uri)
        for key, value in kwargs.items():
            self._ldo.set_option(getattr(ldap, key), value)
        if authtype == auth.simple:
            self._ldo.simple_bind_s(user, password)
        elif authtype == auth.kerb:
            self._ldo.sasl_interactive_bind_s('', ldap.sasl.gssapi())

    def _stripReferences(self, ldif):
        return [x for x in ldif if x[0] is not None]

    def getSingle(self, sbase, sfilter, scope=SCOPE):
        ldif = self._ldo.search_ext_s(sbase, scope, sfilter)
        result = self._stripReferences(ldif)
        if not result:
            raise RuntimeError(textwrap.dedent("""\
                               No results found for single-object query:
                               base: '%s' 
                               filter: '%s'""" %(sbase, sfilter)))
        if len(result) > 1:
            raise RuntimeError(textwrap.dedent("""\
                               Too many results found for single-object query:
                               base: '%s' 
                               filter: '%s'
                               results: '%s'""" %(sbase, sfilter, result)))
        return result[0]

    def getMultiple(self, sbase, sfilter, scope=SCOPE):
        return self._stripReferences(self._ldo.search_ext_s(sbase, scope,
                                                            sfilter))

    def addAttr(self, sbase, dn, attr, value):
        oldobj = self.getSingle(sbase, "dn=%s" %dn)
        newobj = copy.deepcopy(oldobj)
        newobj[1][attr].append(value)
        ml = ldap.modlist.modifyModlist(oldobj, newobj)
        self._ldo.modify_ext_s(dn, ml)

    def rmAttr(self, sbase, dn, attr, value):
        oldobj = self.getSingle(sbase, "dn=%s" %dn)
        newobj = copy.deepcopy(oldobj)
        newobj[1][attr].remove(value)
        ml = ldap.modlist.modifyModlist(oldobj, newobj)
        self._ldo.modify_ext_s(dn, ml)

    def createObj(self, dn, attrs):
        if not attrs:
            raise ValueError("New objects must have at least one attribute")
        self._ldo.add_ext_s(dn, ldap.modlist.addModlist(attrs))

    def deleteObj(self, dn):
        self._ldo.delete_ext_s(dn)
