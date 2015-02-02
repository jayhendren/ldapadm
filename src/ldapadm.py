#!/usr/bin/env python2

import argparse
import yaml
import ldap
import ldap.sasl
import ldap.modlist
import textwrap
import copy

def recursive_merge(a, b):
    """Merge nested dictionary objects. a will be merged into b"""
    for key in a:
        if key in b and isinstance(a[key], dict) and isinstance(b[key], dict):
            recursive_merge(a[key], b[key])
        else:
            b[key] = a[key]

def render_pretty_output(output):
    black          = '\x1b[30m'
    red            = '\x1b[31m'
    green          = '\x1b[32m'
    yellow         = '\x1b[33m'
    blue           = '\x1b[34m'
    magenta        = '\x1b[35m'
    cyan           = '\x1b[36m'
    white          = '\x1b[37m'
    bright_black   = '\x1b[30;1m'
    bright_red     = '\x1b[31;1m'
    bright_green   = '\x1b[32;1m'
    bright_yellow  = '\x1b[33;1m'
    bright_blue    = '\x1b[34;1m'
    bright_magenta = '\x1b[35;1m'
    bright_cyan    = '\x1b[36;1m'
    bright_white   = '\x1b[37;1m'
    reset_color    = '\x1b[39;49m'

    output_str_list = []
    for query, result in output.items():
        header = white + query + reset_color + ':' + '\n'
        results_str = header
        if not result['success']:
            results_str += red + result['message'] + reset_color + '\n'
        else:
            results_str += green + result['message'] + reset_color + '\n'
            for r in result.get('results', {}):
                divider = '-' * 40 + '\n'
                entry = ''
                for k, v in r[1].items():
                    attribute = cyan + "%-18s" % k + reset_color + ': ' 
                    # value_template = magenta + '%s' + reset_color + '\n'
                    if v is None:
                        entry += attribute + magenta + 'None' + \
                                 reset_color + '\n'
                    else:
                        for i in v:
                            entry += attribute + yellow + i + \
                                     reset_color + '\n'
                results_str += divider + entry + divider
        output_str_list.append(results_str)
    output_str = '\n'.join(output_str_list)

    print output_str

def render_yaml_output(output):
    print yaml.dump(output)

class auth():
    kerb, simple, noauth = "kerb_auth", "simple_auth", "no_auth"

SCOPE=ldap.SCOPE_SUBTREE # hardcoded for now; to be moved to configuration

class LDAPObjectManager():

    """
    The LDAPObjectManager class manages an LDAP connection and exposes
    methods to perform common LDAP operations over that connection.

    LDAPObjectManager accepts keyword arguments that are passed on to
    the underlying LDAP object.
    """

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

    def _strip_references(self, ldif):
        return [x for x in ldif if x[0] is not None]

    def get_single(self, sbase, sfilter, scope=SCOPE, attrs=None):
        ldif = self._ldo.search_ext_s(sbase, scope, sfilter, attrlist=attrs)
        result = self._strip_references(ldif)
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

    def get_multiple(self, sbase, sfilter, scope=SCOPE, attrs=None):
        return self._strip_references(self._ldo.search_ext_s(sbase, scope,
            sfilter, attrlist=attrs))

    def add_attribute(self, sbase, dn, attr, *values):
        oldobj = self.get_single(dn, 'objectClass=*')[1]
        newobj = copy.deepcopy(oldobj)
        newobj[attr] = newobj.get(attr, []) + list(values)
        ml = ldap.modlist.modifyModlist(oldobj, newobj)
        self._ldo.modify_ext_s(dn, ml)

    def remove_attribute(self, sbase, dn, attr, *values):
        oldobj = self.get_single(dn, 'objectClass=*')[1]
        newobj = copy.deepcopy(oldobj)
        for v in values:
            newobj[attr].remove(v)
        ml = ldap.modlist.modifyModlist(oldobj, newobj)
        self._ldo.modify_ext_s(dn, ml)

    def create_object(self, dn, attrs):
        if not attrs:
            raise ValueError("New objects must have at least one attribute")
        self._ldo.add_ext_s(dn, ldap.modlist.addModlist(attrs))

    def delete_object(self, dn):
        self._ldo.delete_ext_s(dn)

class LDAPAdminTool():

    """
    The LDAPAdminTool class exposes methods to perform common LDAP
    administrative tasks.  It accepts a configuration object as the sole
    argument to the constructor function.  It does not directly manage
    an LDAP connection or LDAP object; this task is passed off to an
    LDAPObjectManager instance.
    """

    def __init__(self, config):
        self.config = config
        lom_kwargs = self.config.get('options', {})
        auth_str = self._config_get("auth_type", default="noauth")
        auth_type = None
        if auth_str == "noauth":
            auth_type = auth.noauth
        elif auth_str == "kerb":
            auth_type = auth.kerb
        elif auth_str == "simple":
            auth_type = auth.simple
            lom_kwargs['user'] = self._config_get('username')
            lom_kwargs['password'] = self._config_get('password')
        self._lom = LDAPObjectManager(self._config_get('uri'),
                                      auth_type,
                                      **lom_kwargs)

    def _config_get(self, *args, **kwargs):
        default = kwargs.get('default')
        cursor = self.config
        for a in args:
            if cursor is default: break
            cursor = cursor.get(a, default)
        return cursor

    def _build_query(self, fields, values):
        return "(|%s)" % "".join(["(%s=%s)" % (f, v) for v in values \
                                  for f in fields])
    
    def _get_single(self, item_type, search_term, attrs=None):
        return self._lom.get_single(self._config_get(item_type, 'base'),
            "%s=%s" %(self._config_get(item_type, 'identifier'), search_term),
            attrs=attrs)

    def _add_missing_attributes(self, object, item_type):
        for attr in self._config_get(item_type, 'display', default=[]):
            if object[1].get(attr) is None:
                object[1][attr] = None

    def _get_dn(self, item_type, name):
        return'%s=%s,%s' %(self._config_get(item_type, 'identifier'),
                           name,
                           self._config_get(item_type, 'base'))

    def get(self, item_type, *search_terms):
        results = {}
        for t in search_terms:
            success = True
            message = None
            obj = self._get_single(item_type, t,
                attrs=self._config_get(item_type, 'display'))
            # add blank attrs for attrs in display list that aren't on object
            self._add_missing_attributes(obj, item_type)
            if success:
                message = "Found result for \"%s\"" % t
            else:
                message = "Did not find result for \"%s\"" % t
            results[t] = {'results': [list(obj)],
                          'success': success,
                          'message': message}
        return results

    def search(self, item_type, *search_terms):
        output_obj = {}
        for t in search_terms:
            success = True
            message = None
            query = self._build_query(self._config_get(item_type, search),
                                     ['%s*' % t])
            base = self._config_get(item_type, 'base')
            results = self._lom.get_multiple(base, query,
                attrs=self._config_get(item_type, 'display'))
            for obj in results:
                self._add_missing_attributes(obj, item_type)
            if not results:
                success = False
                message = "Did not find result for \"%s\"" % t
            else:
                message = "Found result(s) for \"%s\"" % t
            output_obj[t] = {'results': [list(r) for r in results],
                             'success': success,
                             'message': message}
        return output_obj

    def create(self, item_type, *names):
        results = {}
        for name in names:
            success = True
            message = None
            dn = self._get_dn(item_type, name)
            attrs = self._config_get(item_type, 'schema')
            self._lom.create_object(dn, attrs)
            if success:
                message = "Created object %s." %dn
            else:
                message = "Failed to create object %s." %dn
            results[name] = {'success': success, 'message': message}
        return results

    def delete(self, item_type, *names):
        results = {}
        for name in names:
            success = True
            message = None
            dn = self._get_dn(item_type, name)
            self._lom.delete_object(dn)
            if success:
                message = "Deleted object %s." %dn
            else:
                message = "Failed to delete object %s." %dn
            results[name] = {'success': success, 'message': message}
        return results

    def _insert_or_remove(self, action, group_type, group_name,
                          member_type, *member_names):
        success = True
        message = None
        result = {}
        group_dn = self._get_single(group_type, group_name)[0]
        member_dns = []
        for name in member_names:
            member_dns.append(self._get_single(member_type, name)[0])
        if action == insert:
            func = self._lom.add_attribute
        elif action == remove:
            func = self._lom.remove_attribute
        func(self._config_get(group_type, 'base'),
             group_dn, 
             self._config_get(group_type, 'member', default='member'),
             *member_dns)
        for name in member_names:
            if success:
                if action == insert:
                    message = "%s inserted into group %s" %(name, group_name)
                elif action == remove:
                    message = "%s removed from group %s" %(name, group_name)
            else:
                if action == insert:
                    message = "%s not inserted into group %s" \
                              %(name, group_name)
                elif action == remove:
                    message = "%s not removed from group %s" \
                              %(name, group_name)
            result[name] = {'success': success, 'message': message}
        return result

    def insert(self, *args, **kwargs):
        return self._insert_or_remove(insert, *args, **kwargs)

    def remove(self, *args, **kwargs):
        return self._insert_or_remove(remove, *args, **kwargs)

if __name__ == '__main__':

    # command literals
    get    = 'get'
    search = 'search'
    create = 'create'
    delete = 'delete'
    insert = 'insert'
    remove = 'remove'

    def get_new_parser():
        return argparse.ArgumentParser(add_help=False)

    single_type_parser = get_new_parser()
    single_type_parser.add_argument('object_type', help="""
        Type, as specified in configuration, of the object to perform an
        action on.""")
    single_type_parser.add_argument('object_name', nargs="+", help="""
        Name of the object to perform an action on.  The name will be searched
        for in the the attribute specified by the "identifier" field for this 
        object's type as provided by configuration.""")

    double_type_parser = get_new_parser()
    double_type_parser.add_argument('group_object_type', help="""
        Type, as specified in configuration, of the group object to perform an
        action on.""")
    double_type_parser.add_argument('group_object_name', help="""
        Name of the group to perform an action on. The name will be searched
        for in the the attribute specified by the "identifier" field for this 
        object's type as provided by configuration.""")
    double_type_parser.add_argument('member_object_type', help="""
        Type, as specified in configuration, of the member object(s).""")
    double_type_parser.add_argument('member_object_name', nargs="+", help="""
        Name of the member(s) to perform an action on. The name will be
        searched for in the the attribute specified by the "identifier" field
        for this object's type as provided by configuration.""")
    
    parser = argparse.ArgumentParser(description="""
        A command-line tool to perform common LDAP administrative tasks,
        such as fetching objects and their attributes, adding and removing
        members from a group, and creating and deleting objects. Online
        documentation is available at:

        https://stash.int.colorado.edu/projects/SIS/repos/ldapadm/browse""",
        epilog="""
        For help on a specific command, run "%(prog)s <command> -h".""" )

    parser.add_argument('-c', '--config',
        default='/etc/ldapadm.conf.yaml',
        help="""Path to a YAML-formatted configuration file.  See the online
                documentation for more information on the configuration file
                format.  Default path is %(default)s""")

    parser.add_argument('-o', '--options',
        action='append',
        default=[],
        help="""YAML-formatted configuration supplied on the command line.
                Format of command-line-supplied configuration is identical to
                that of the configuration file.  Any configuration options
                supplied on the command line will override settings provided
                in the configuration file.""")

    parser.add_argument('-r', '--pretty',
        action='store_true',
        help="""Print pretty, colorful, easy-to-read output instead of
                YAML-formatted output.""")

    auth_group = parser.add_mutually_exclusive_group()

    auth_group.add_argument('-k', '--kerb',
        action='store_true',
        help='Use kerberos authentication.')

    auth_group.add_argument('-u', '--username',
        help="""Username to be used for simple authentication. If present,
                simple authentication will be used.""")

    parser.add_argument('-p', '--password',
        help='Password to be used for simple authentication.')

    auth_group.add_argument('-n', '--no-auth',
        action='store_true',
        help='Do not use authentication. Attempt an anonymous bind.')

    subparser = parser.add_subparsers(dest='command')
    
    parser_get = subparser.add_parser(get, parents=[single_type_parser],
        description="""Retrieve a single entry per name argument provided.
                       It is considered an error if not exactly one object
                       is retrieved per name argument.""")
    parser_search = subparser.add_parser(search, parents=[single_type_parser],
        description="""Perform a search query.  Zero or more results may be
                       returned per query.""")
    parser_create = subparser.add_parser(create, parents=[single_type_parser],
        description="""Create a new object.""")
    parser_delete = subparser.add_parser(delete, parents=[single_type_parser],
        description="""Delete an existing object.""")
    parser_insert = subparser.add_parser(insert, parents=[double_type_parser],
        description="""Insert members (of any type) into a group object.""")
    parser_remove = subparser.add_parser(remove, parents=[double_type_parser],
        description="""Remove members (of any type) from a group object.""")

    args = parser.parse_args()

    config_path = args.config
    config = yaml.load(file(config_path, 'r'))
    for o in args.options:
        c = yaml.load(o)
        recursive_merge(c, config)

    if args.kerb:
        config['auth_type'] = 'kerb'
    elif args.username is not None:
        config['auth_type'] = 'simple'
        config['username'] = args.username
        config['password'] = args.password
    elif args.no_auth:
        config['auth_type'] = 'noauth'

    lat = LDAPAdminTool(config)

    out = None

    if args.command == get:
        out = lat.get(args.object_type, *args.object_name)
    elif args.command == search:
        out = lat.search(args.object_type, *args.object_name)
    elif args.command == create:
        out = lat.create(args.object_type, *args.object_name)
    elif args.command == delete:
        out = lat.delete(args.object_type, *args.object_name)
    elif args.command == insert:
        lat.insert(args.group_object_type, args.group_object_name,
                   args.member_object_type, *args.member_object_name)
    elif args.command == remove:
        lat.remove(args.group_object_type, args.group_object_name,
                   args.member_object_type, *args.member_object_name)
    else:
        pass

    if args.pretty:
        render_pretty_output(out)
    else:
        render_yaml_output(out)
