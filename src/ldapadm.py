#!/usr/bin/env python2

import argparse
import yaml
from ldapobjectmanager import LDAPObjectManager, auth

def get_user(args, conf, ldo):
    usernames = args.username
    output_obj = {}
    for u in usernames:
        obj = ldo.getSingle(conf['user']['base'],
                            "%s=%s" %(conf['user']['identifier'], u))
        output_obj[u] = {}
        for item in conf['user']['display']:
            output_obj[u][item] = obj[1].get(item)
    print yaml.dump(output_obj)

def get_group(args, conf, ldo):
    pass

def get_access(args, conf, ldo):
    pass

# parent parser for arguments that are common to all sub-commands
parent_parser = argparse.ArgumentParser(add_help=False)

# parent parser for user, group, and access sub-commands
user_parser = argparse.ArgumentParser(parents=[parent_parser],
                                      add_help=False)
user_parser.add_argument('username', nargs="+")
group_parser = argparse.ArgumentParser(parents=[parent_parser],
                                       add_help=False)
group_parser.add_argument('group', nargs="+")
access_parser = argparse.ArgumentParser(parents=[parent_parser],
                                        add_help=False)
access_parser.add_argument('hostname', nargs="+")

def add_command(subparser, command, function, **kwargs):
    parser = subparser.add_parser(command, **kwargs)
    parser.set_defaults(func=function)
    return parser

# main parser object
parser = argparse.ArgumentParser()

parser.add_argument('-c', '--config', nargs=1,
                    help='path to a YAML-formatted configuration file')

subparser = parser.add_subparsers()

# get commands
parser_get = subparser.add_parser('get')
subparser_get = parser_get.add_subparsers()
add_command(subparser_get, 'user', get_user, parents=[user_parser],
            description='get user description')
add_command(subparser_get, 'group', get_group, parents=[group_parser],
            description='get group description')
add_command(subparser_get, 'access', get_access, parents=[access_parser],
            description='get access description')

# search commands
parser_search = subparser.add_parser('search')
subparser_search = parser_search.add_subparsers()
parser_search_user = subparser_search.add_parser('user')
parser_search_group = subparser_search.add_parser('group')
parser_search_access = subparser_search.add_parser('access')

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
subparser_insert = parser_insert.add_subparsers()
parser_insert_group = subparser_insert.add_parser('group')
parser_insert_access = subparser_insert.add_parser('access')

# remove commands
parser_remove = subparser.add_parser('remove')
subparser_remove = parser_remove.add_subparsers()
parser_remove_group = subparser_remove.add_parser('group')
parser_remove_access = subparser_remove.add_parser('access')

args = parser.parse_args()

conf_path = args.config[0]
conf = yaml.load(file(conf_path, 'r'))
ldo = LDAPObjectManager(conf['uri'], auth.noauth)

args.func(args, conf, ldo)
