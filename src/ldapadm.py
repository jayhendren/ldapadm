#!/usr/bin/env python2

import argparse
import yaml
from ldapobjectmanager import LDAPObjectManager, auth

class LDAPAdminTool():

    def __init__(self, config):
        self.config = config
        self.lom = LDAPObjectManager(self.config['uri'], auth.simple,
                                user=self.config['username'],
                                password=self.config['password'],
                                **self.config.get('options', {}))

    def build_query(self, fields, values):
        return "(|%s)" % "".join(["(%s=%s)" % (f, v) for v in values \
                                  for f in fields])
    
    def get_item(self, item_type, search_term, attrs=None):
        return self.lom.getSingle(self.config[item_type]['base'],
            "%s=%s" %(self.config[item_type]['identifier'], search_term),
            attrs=attrs)

    def add_missing_attributes(self, object, item_type):
        for attr in self.config[item_type].get('display', []):
            if object[1].get(attr) is None:
                object[1][attr] = None

    def get_items(self, item_type, *search_terms):
        output_obj = {}
        for t in search_terms:
            obj = self.get_item(item_type, t,
                                attrs=self.config[item_type].get('display'))
            # add blank attrs for attrs in display list that aren't on object
            self.add_missing_attributes(obj, item_type)
            output_obj[t] = list(obj)
        return output_obj

    def search(self, item_type, *search_terms):
        output_obj = {}
        for t in search_terms:
            query = self.build_query(self.config[item_type]['search'],
                                     ['%s*' % t])
            results = self.lom.getMultiple(self.config[item_type]['base'],
                query,
                attrs=self.config[item_type].get('display'))
            for obj in results:
                self.add_missing_attributes(obj, item_type)
            output_obj[t] = [list(r) for r in results]
        return output_obj

    def insert(self, group_type, group_name, *usernames):
        group_dn = self.get_item(group_type, group_name)[0]
        user_dns = []
        for name in usernames:
            user_dns.append(self.get_item('user', name)[0])
        self.lom.addAttr(self.config[group_type]['base'],
                         group_dn, 
                         self.config[group_type].get('member', 'member'),
                         *user_dns)

    def remove(self, group_type, group_name, *usernames):
        group_dn = self.get_item(group_type, group_name)[0]
        user_dns = []
        for name in usernames:
            user_dns.append(self.get_item('user', name)[0])
        self.lom.rmAttr(self.config[group_type]['base'],
                         group_dn, 
                         self.config[group_type].get('member', 'member'),
                         *user_dns)

if __name__ == '__main__':

    # parent parser for arguments that are common to all sub-commands
    parent_parser = argparse.ArgumentParser(add_help=False)
    
    # parent parser for user, group, access, etc. sub-commands
    user_parser = argparse.ArgumentParser(parents=[parent_parser],
                                          add_help=False)
    user_parser.add_argument('username', nargs="+")
    group_parser = argparse.ArgumentParser(parents=[parent_parser],
                                           add_help=False)
    group_parser.add_argument('group', nargs="+")
    access_parser = argparse.ArgumentParser(parents=[parent_parser],
                                            add_help=False)
    access_parser.add_argument('hostname', nargs="+")
    group_mod_parser = argparse.ArgumentParser(parents=[parent_parser],
                                           add_help=False)
    group_mod_parser.add_argument('group')
    group_mod_parser.add_argument('username', nargs="+")
    access_mod_parser = argparse.ArgumentParser(parents=[parent_parser],
                                           add_help=False)
    access_mod_parser.add_argument('hostname')
    access_mod_parser.add_argument('username', nargs="+")
    
    # main parser object
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
        help='path to a YAML-formatted configuration file')
    subparser = parser.add_subparsers(dest='command')
    
    # get commands
    parser_get = subparser.add_parser('get', parents=[parent_parser])
    subparser_get = parser_get.add_subparsers(dest='get_command')
    parser_get_user = subparser_get.add_parser('user',
        parents=[user_parser],
        description='get user description')
    parser_get_group = subparser_get.add_parser('group',
        parents=[group_parser],
        description='get group description')
    parser_get_access = subparser_get.add_parser('access',
        parents=[access_parser],
        description='get access description')
    
    # search commands
    parser_search = subparser.add_parser('search')
    subparser_search = parser_search.add_subparsers(dest='search_command')
    parser_search_user = subparser_search.add_parser('user',
        parents=[user_parser],
        description='search user description')
    parser_search_group = subparser_search.add_parser('group',
        parents=[group_parser],
        description='search group description')
    parser_search_access = subparser_search.add_parser('access',
        parents=[access_parser],
        description='search access description')
    
    # create commands
    parser_create = subparser.add_parser('create')
    subparser_create = parser_create.add_subparsers()
    parser_create_user = subparser_create.add_parser('user')
    parser_create_group = subparser_create.add_parser('group')
    parser_create_access = subparser_create.add_parser('access')
    
    # delete commands
    parser_delete = subparser.add_parser('delete')
    subparser_delete = parser_delete.add_subparsers()
    parser_delete_user = subparser_delete.add_parser('user')
    parser_delete_group = subparser_delete.add_parser('group')
    parser_delete_access = subparser_delete.add_parser('access')
    
    # insert commands
    parser_insert = subparser.add_parser('insert')
    subparser_insert = parser_insert.add_subparsers(dest='insert_command')
    parser_insert_group = subparser_insert.add_parser('group',
                              parents=[group_mod_parser])
    parser_insert_access = subparser_insert.add_parser('access',
                              parents=[access_mod_parser])
    
    # remove commands
    parser_remove = subparser.add_parser('remove')
    subparser_remove = parser_remove.add_subparsers(dest='remove_command')
    parser_remove_group = subparser_remove.add_parser('group',
                              parents=[group_mod_parser])
    parser_remove_access = subparser_remove.add_parser('access',
                              parents=[access_mod_parser])
    
    args = parser.parse_args()

    config_path = args.config
    config = yaml.load(file(config_path, 'r'))
    lat = LDAPAdminTool(config)

    out = None

    def render_output(output):
        print yaml.dump(output)

    if args.command == 'get':
        if args.get_command == 'user':
            out = lat.get_items('user', *args.username)
        elif args.get_command == 'group':
            out = lat.get_items('group', *args.group)
        elif args.get_command == 'access':
            out = lat.get_items('access', *args.hostname)
    elif args.command == 'search':
        if args.search_command == 'user':
            out = lat.search('user', *args.username)
        elif args.search_command == 'group':
            out = lat.search('group', *args.group)
        elif args.search_command == 'access':
            out = lat.search('access', *args.hostname)
    elif args.command == 'create':
        pass
    elif args.command == 'delete':
        pass
    elif args.command == 'insert':
        if args.insert_command == 'group':
            lat.insert('group', args.group, *args.username)
        elif args.insert_command == 'access':
            lat.insert('access', args.hostname, *args.username)
    elif args.command == 'remove':
        if args.remove_command == 'group':
            lat.remove('group', args.group, *args.username)
        elif args.remove_command == 'access':
            lat.remove('access', args.hostname, *args.username)
    else:
        pass

    render_output(out)
