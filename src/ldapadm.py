#!/usr/bin/env python2

import argparse
import yaml
from ldapobjectmanager import LDAPObjectManager, auth

def recursive_merge(a, b):
    """Merge nested dictionary objects. a will be merged into b"""
    for key in a:
        if key in b:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                recursive_merge(a[key], b[key])
            else:
                raise ValueError('Cannot merge: %s and %s' %(a[key], b[key]))
        else:
            b[key] = a[key]

def render_yaml_output(output):
    print yaml.dump(output)

class LDAPAdminTool():

    def __init__(self, config):
        self.config = config
        self.lom = LDAPObjectManager(self._config_get('uri'),
                                     auth.simple,
                                     user=self._config_get('username'),
                                     password=self._config_get('password'),
                                     **self.config.get('options', {}))

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
        return self.lom.getSingle(self._config_get(item_type, 'base'),
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
        output_obj = {}
        for t in search_terms:
            obj = self._get_single(item_type, t,
                attrs=self._config_get(item_type, 'display'))
            # add blank attrs for attrs in display list that aren't on object
            self._add_missing_attributes(obj, item_type)
            output_obj[t] = list(obj)
        return output_obj

    def search(self, item_type, *search_terms):
        output_obj = {}
        for t in search_terms:
            query = self._build_query(self._config_get(item_type, search),
                                     ['%s*' % t])
            results = self.lom.getMultiple(self._config_get(item_type, 'base'),
                query,
                attrs=self._config_get(item_type, 'display'))
            for obj in results:
                self._add_missing_attributes(obj, item_type)
            output_obj[t] = [list(r) for r in results]
        return output_obj

    def create(self, item_type, name):
        dn = self._get_dn(item_type, name)
        attrs = self._config_get(item_type, 'schema')
        self.lom.createObj(dn, attrs)

    def delete(self, item_type, name):
        dn = self._get_dn(item_type, name)
        self.lom.deleteObj(dn)

    def _insert_or_remove(self, action, group_type, group_name,
                          member_type, *member_names):
        group_dn = self._get_single(group_type, group_name)[0]
        member_dns = []
        for name in member_names:
            member_dns.append(self._get_single(member_type, name)[0])
        if action == insert:
            func = self.lom.addAttr
        elif action == remove:
            func = self.lom.rmAttr
        func(self._config_get(group_type, 'base'),
             group_dn, 
             self._config_get(group_type, 'member', default='member'),
             *member_dns)

    def insert(self, *args, **kwargs):
        self._insert_or_remove(insert, *args, **kwargs)

    def remove(self, *args, **kwargs):
        self._insert_or_remove(remove, *args, **kwargs)

if __name__ == '__main__':

    # command literals
    get    = 'get'
    search = 'search'
    create = 'create'
    delete = 'delete'
    insert = 'insert'
    remove = 'remove'

    # parent parser holds arguments that are common to all sub-commands
    parent_parser = argparse.ArgumentParser(add_help=False)

    def get_new_parser():
        return argparse.ArgumentParser(parents=[parent_parser], add_help=False)

    single_type_parser = get_new_parser()
    single_type_parser.add_argument('object_type')
    single_type_parser.add_argument('object_name', nargs="+")

    double_type_parser = get_new_parser()
    double_type_parser.add_argument('group_object_type')
    double_type_parser.add_argument('group_object_name')
    double_type_parser.add_argument('member_object_type')
    double_type_parser.add_argument('member_object_name', nargs="+")
    
    # main parser object
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
        help='path to a YAML-formatted configuration file')
    parser.add_argument('-o', '--options',
        action='append',
        default=[],
        help='YAML-formatted configuration supplied on the command line')
    subparser = parser.add_subparsers(dest='command')
    
    parser_get = subparser.add_parser(get, parents=[single_type_parser])
    parser_search = subparser.add_parser(search, parents=[single_type_parser])
    parser_create = subparser.add_parser(create, parents=[single_type_parser])
    parser_delete = subparser.add_parser(delete, parents=[single_type_parser])
    parser_insert = subparser.add_parser(insert, parents=[double_type_parser])
    parser_remove = subparser.add_parser(remove, parents=[double_type_parser])

    args = parser.parse_args()

    config_path = args.config
    config = yaml.load(file(config_path, 'r'))
    for o in args.options:
        c = yaml.load(o)
        recursive_merge(c, config)

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

    render_yaml_output(out)
