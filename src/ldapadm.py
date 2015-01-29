#!/usr/bin/env python2

import argparse
import yaml
from ldapobjectmanager import LDAPObjectManager, auth

# object types
user   = 'user'
group  = 'group'
access = 'access'

# commands
get    = 'get'
search = 'search'
create = 'create'
delete = 'delete'
insert = 'insert'
remove = 'remove'

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

    def _insert_or_remove(self, action, group_type, group_name, *usernames):
        group_dn = self._get_single(group_type, group_name)[0]
        user_dns = []
        for name in usernames:
            user_dns.append(self._get_single(user, name)[0])
        if action == insert:
            func = self.lom.addAttr
        elif action == remove:
            func = self.lom.rmAttr
        func(self._config_get(group_type, 'base'),
             group_dn, 
             self._config_get(group_type, 'member', default='member'),
             *user_dns)

    def insert(self, *args, **kwargs):
        self._insert_or_remove(insert, *args, **kwargs)

    def remove(self, *args, **kwargs):
        self._insert_or_remove(remove, *args, **kwargs)

if __name__ == '__main__':

    # parent parser for arguments that are common to all sub-commands
    parent_parser = argparse.ArgumentParser(add_help=False)
    
    # parent parser for user, group, access, etc. sub-commands
    arg1 = 'arg1'
    arg2 = 'arg2'

    def get_new_parser():
        return argparse.ArgumentParser(parents=[parent_parser], add_help=False)

    user_parser = get_new_parser()
    user_parser.add_argument(arg1, nargs="+", metavar='username')

    group_parser = get_new_parser()
    group_parser.add_argument(arg1, nargs="+", metavar='group')

    access_parser = get_new_parser()
    access_parser.add_argument(arg1, nargs="+", metavar='hostname')

    group_mod_parser = get_new_parser()
    group_mod_parser.add_argument(arg1, metavar='group')
    group_mod_parser.add_argument(arg2, nargs="+", metavar='username')

    access_mod_parser = get_new_parser()
    access_mod_parser.add_argument(arg1, metavar='hostname')
    access_mod_parser.add_argument(arg2, nargs="+", metavar='username')
    
    # main parser object
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
        help='path to a YAML-formatted configuration file')
    subparser = parser.add_subparsers(dest='command')
    
    # get commands
    parser_get = subparser.add_parser(get, parents=[parent_parser])
    subparser_get = parser_get.add_subparsers(dest='get_command')
    parser_get_user = subparser_get.add_parser(user,
        parents=[user_parser],
        description='get user description')
    parser_get_group = subparser_get.add_parser(group,
        parents=[group_parser],
        description='get group description')
    parser_get_access = subparser_get.add_parser(access,
        parents=[access_parser],
        description='get access description')
    
    # search commands
    parser_search = subparser.add_parser(search)
    subparser_search = parser_search.add_subparsers(dest='search_command')
    parser_search_user = subparser_search.add_parser(user,
        parents=[user_parser],
        description='search user description')
    parser_search_group = subparser_search.add_parser(group,
        parents=[group_parser],
        description='search group description')
    parser_search_access = subparser_search.add_parser(access,
        parents=[access_parser],
        description='search access description')
    
    # create commands
    parser_create = subparser.add_parser(create)
    subparser_create = parser_create.add_subparsers()
    parser_create_user = subparser_create.add_parser(user)
    parser_create_group = subparser_create.add_parser(group)
    parser_create_access = subparser_create.add_parser(access)
    
    # delete commands
    parser_delete = subparser.add_parser(delete)
    subparser_delete = parser_delete.add_subparsers()
    parser_delete_user = subparser_delete.add_parser(user)
    parser_delete_group = subparser_delete.add_parser(group)
    parser_delete_access = subparser_delete.add_parser(access)
    
    # insert commands
    parser_insert = subparser.add_parser(insert)
    subparser_insert = parser_insert.add_subparsers(dest='insert_command')
    parser_insert_group = subparser_insert.add_parser(group,
                              parents=[group_mod_parser])
    parser_insert_access = subparser_insert.add_parser(access,
                              parents=[access_mod_parser])
    
    # remove commands
    parser_remove = subparser.add_parser(remove)
    subparser_remove = parser_remove.add_subparsers(dest='remove_command')
    parser_remove_group = subparser_remove.add_parser(group,
                              parents=[group_mod_parser])
    parser_remove_access = subparser_remove.add_parser(access,
                              parents=[access_mod_parser])

    # parse arguments
    args = parser.parse_args()

    # load configuration
    config_path = args.config
    config = yaml.load(file(config_path, 'r'))
    lat = LDAPAdminTool(config)

    # run command
    out = None

    if args.command == get:
        out = lat.get(args.get_command, *args.arg1)
    elif args.command == search:
        out = lat.search(args.search_command, *args.arg1)
    elif args.command == create:
        pass
    elif args.command == delete:
        pass
    elif args.command == insert:
        lat.insert(args.insert_command, args.arg1, *args.arg2)
    elif args.command == remove:
        lat.remove(args.remove_command, args.arg1, *args.arg2)
    else:
        pass

    # render output
    render_yaml_output(out)
