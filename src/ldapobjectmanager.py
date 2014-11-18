import ldap

class auth():
    kerb, simple, noauth = range(3)

class LDAPObjectManager():

    def __init__(self, uri, authtype, **kwargs):
        pass

    def gets(self, base, filter):
        raise RuntimeError
