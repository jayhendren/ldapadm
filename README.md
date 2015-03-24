# ldapadm

A command-line tool for performing common administrative tasks on an
LDAP server, such as retrieving information about objects, creating and
deleting objects, and adding and removing objects from group membership.

## Requirements

* Python 2.7
* [python-ldap](http://www.python-ldap.org/)
* [pyyaml](http://pyyaml.org/)

For development purposes only:

* [python-ldap-test](https://github.com/zoldar/python-ldap-test/) (A Python
  wrapper around the UnboundID in-memory LDAP server.  Requires Java.)
* (optional) [watchdog](http://pythonhosted.org/watchdog/)

## Usage

ldapadm commands are typically run with the following syntax:

    $ ldapadm --flags command object_type object_name

The following commands are available:

* `get` - to fetch a single object and view its attributes
* `search` - to run a search against the LDAP server and view the
  attributes of all returned objects
* `create` - to create a new object using a user-supplied schema
* `delete` - to delete an existing object
* `insert` - to insert an object into group membership
* `remove` - to remove an object from group membership

The user must supply at least one object type in configuration.  For most
LDAP servers/schema, the user will likely wish to use types called "user",
"group", "computer", and so on.  The `object_type` argument refers to
one of these user-supplied types.

`object_name` is the name of the object being acted upon.  The
user-supplied configuration will determine how to map a combination
of name and type to an object, though (hopefully) sane defaults are
available that should work for most LDAP schema.

To see all available flags and options, run `ldapadm -h` or `ldapadm
--help`.  To see the argument syntax for a specific command, or for more
specific help on a particular command, run `ldapadm command -h` or
`ldapadm command --help`.

## Output

To improve inter-process operability, ldapadm generates YAML-formatted
output.  The following object structure is used for the output of all
commands (in pseudo-YAML format):

    query1:
      success: true|false
      message: "a simple message about the result of the command"
      results:
        - - "distinguished name of the first object"
          - attribute1: ["value1", "value2", ... ]
          - attribute2: ["value3", ...]
          - attribute_with_no_value: null
        - - "distinguished name of the second object"
          - ...
        ...
    query2:
      ...
    ...

* Each key in the top-level object is one of the name or query arguments
  to the command.  For instance, in the command `ldapadm get user alice bob
  carol`, the keys will be `alice`, `bob`, and `carol`.  For the command
  `ldapadm insert group hackers user dave edgar felicia`, the keys will be
  `dave`, `edgar`, and `felicia`.

* The value for each key is another object.  This object will always
  have the key `success`, which is a boolean (`true` or `false`) value
  indicating whether the requested operation completed successfully.
  `message` contains diagnostic information.  The `results` key deserves
  its own bullet point:

* `results` does not exist in the output of all commands.  Only commands
  that return LDAP objects, specifically the `get` and `search` commands,
  will populate `results`.  `results` will always be a list (in the case
  of the `get` command, this list is guaranteed to be of length 1).
  Each object in the list is an LDAP object, which is itself a list
  containing two values: the first value is the distinguished name ("dn") of
  the object, and the second value is a mapping of the object's attributes.
  The value for each attribute is always either a list or the value "null"
  (the value "null" occurs when the user requests to display an attribute
  via configuration, but that attribute does not exist on the object).
  Each value in the list is a string.

You can also choose to make the output more colorful and easy-to-read
(but break machine-readability) by using the `-r` or `--pretty` flag:

![pretty output](doc/output_pretty.png)

## Configuration

The heart of the ldapadm tool is configuration.  Although ldapadm doesn't
offer any more functionality than OpenLDAP command-line client tools
(for instance), once ldapadm is properly configured, the user need not
know anything about LDAP schemas or the LDAP protocol.

Configuration must be in YAML format.  Configuration can be stored
in a file or supplied on the command line.  The default path for the
configuration file is `/etc/ldapadm.conf.yaml`.  The configuration
file path can be changed using the `-c` or `--config` option at the
command line.  See below for how to supply configuration directly on
the command line using the `-o` or `--options` flag.

Here is the configuration schematic and a description for each of the
configuration options:

    uri: "ldaps://my.domain:636"
    base: "dc=my,dc=domain"
    options:
        <option1>: <value1>
        <option2>: <value2>
    <type>:
      base: "ou=people,dc=my,dc=domain"
      scope: "one_level"
      member: "member"
      member_matching_rule_in_chain: false
      member_of: "memberOf"
      member_of_matching_rule_in_chain: true
      schema:
           <attribute1>: <value1>
           <attribute2>: <value2>
      identifier: cn
      search: [cn, sn, title, description, uidnumber]
      filter: "objectclass=user"
      display: [cn, sn, title, description, uidnumber]

* `uri`: A string containing the URI of the LDAP server.  May contain a
  scheme identifier (e.g., `ldap://` or `ldaps://`) and a port (e.g. `:389`,
  `636`). **Required**

* `base`: A string containing the Distinguished Name (DN) of the base
  object for all LDAP queries.

* `options`: A mapping of options and their values that are passed
  directly on to the python-ldap library.  For instance:

      options:
        OPT_REFERRALS: "0"
        OPT_X_TLS_CACERTDIR: "/usr/local/openssl/certs"

  These two options prevent following referrals and set the directory
  that contains trusted SSL CA certificates, respectively.

  The available options are identical to the options
  exposed by the underlying python-ldap library.  More
  information on the options is available in the [python-ldap
  documentation](http://www.python-ldap.org/doc/html/ldap.html#options).
  Note that all options start with `OPT_`.

* `<type>`: This is the name of the user-supplied object type.  You will
  probably want to use a type name that clearly references a specific type
  of object on the LDAP server.  This will also be the value that you pass
  as the "type" argument to the various ldapadm commands.  For instance,
  if you wish to be able to run the commands `ldapadm get user ...` and
  `ldapadm get group ...`, you must define the types `user` and `group`
  in your configuration.  For instance:

      user:
        base: "ou=people,dc=my,dc=domain"
        ...

  A type definition may include the following values:

  * `base`: the DN of the base object for objects of this type.  **Default:
    the value of the parent `base` setting or ""**.  Note that a blank base
    DN in queries may cause some LDAP servers to reject the query.

  * `scope`: the scope of queries for objects of this type.  Choose from:

    * `base`: only search the base object.  Not recommended unless the base
      object is the only object of this type.
    * `one_level`: only search the base object and children of the base object.
    * `subtree`: search all children of the base object, recursively.

    **Default: `subtree`**

    **Not yet implemented**.  This is a planned feature; at the moment,
    the value is hardcoded at `subtree`.

  * `member`:  the name of the attribute that contains a list of member
    objects.  Used only in insert and remove commands.  **Default: `member`**

  * `memberOf`:  the name of the attribute that contains a list of objects
    that the object is a member of.  Used only in insert and remove commands.
    **Default: `memberOf`**

  * `member_oid` and `member_of_oid`: A boolean value.  These are
    Active Directory-specific and may break other server types.  In a
    nutshell, setting these values to `true` enables searching nested
    group memberships in Active Directory.  See the [MSDN documentation](https://msdn.microsoft.com/en-us/library/aa746475%28v=vs.85%29.aspx) for more info.
    **Default: `false`**
  
  * `identifier`:  the type of RDN ("Relative Distinguished Name") used as the
    primary key to identify this type of object.  Typically, the RDN is an
    attribute whose value is unique per object and constant over time, such as
    `uid`, `cn`, `ou`, and so on.  **Default: cn**

  * `schema`: Used only when creating new objects.  The schema must be
    a mapping of attributes to their values for the new object.  The best
    way to use this option is to configure the common values that should
    be set for all new objects of this type, and then use command-line
    configuration options to add additional values that need to be unique
    for each new object.  See [Examples](#Examples) for examples of creating
    objects using the `schema` configuration value.  A couple more notes:
  
    * values in the schema must be in a list, even if they are single-valued.
      For instance: `cn: [john]`, `sn: [doe]`

    * attributes must be strings.  This means uids and gids must be
      quoted to avoid being interpreted by the YAML parser as numbers.
      For instance: `uidNumber: ['12345']`, `gidNumber: ['12345']`

    **Default: an empty dictionary (`{}`)**
  
  * `search`: A list of attributes that will be searched when running
    the `search` command.  Note that a wildcard will be added after each
    search argument, so a search may not return an exact attribute match.
    Wildcards are not added before the search arguments, as this causes
    queries to hang or return a "too many results" error on some LDAP servers.
    **Default: an empty list (`[]`)**

  * `filter`: This is an ldap search filter that will be applied to all
    lookups, which means that it will affect not only results from `get`
    and `search` commands, but also the objects acted upon in `insert` and
    `remove` commands.  **Default: none**.  **Not yet implemented**.

  * `display`: The attributes to display for objects of this type, for
    instance, in the output of the `get` and `search` commands.  If this
    option is absent or `null`, all attributes will be returned.  If an
    attribute is listed in this option but not present on an object, the
    value for that attribute will be `null` in the output.
    **Default: `null`**

An example configuration file can be found in the [Examples](#Examples)
section.

Configuration can also be supplied on the command line with an argument
to the `-o` or `--options` flag.  The argument must be a YAML-formatted
string with the same structure as above.  Any configuration options
supplied this way will merge with and override options supplied in the
configuration file.

Examples of using the `-o` flag are available in the [Examples](#Examples)
section.

## Examples

*More examples coming soon.*

Here are a couple examples of configuration supplied using the `-o` flag:

* `ldapadm -o "uri: 'ldaps://foo.bar'" get user foobar`
* `ldapadm -o "{user: {schema: {cn: ['john'], sn: ['doe']}}}" create
   user johndoe`
