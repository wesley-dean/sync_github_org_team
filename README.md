# Synchronize GitHub Organization and Team Membership

This is a tool to synchronize the membership of a GitHub
team with a GitHub organization.  That is, when run, it
will query GitHub for the list of members of the
organization and add them to a team under that
organization.

## Reason for this tool

Access to repositories can be provided to individual
users or teams, but not organizations.  There may be
situations where an organization wants to provide
access to a repository to all of their users but
not the general public -- they want to "internally
open-source" or
[InnerSource](https://resources.github.com/software-development/innersource/)
resources.  This tool fills in the gap -- the
missing ability to specify organization-wide
access -- by creating a team that may be used.

## Installing the tool

There are several Python modules required to run the
tool, all of which may be installed via PyPI (pip)
or, in some instances, the operating system's package
manager (e.g., `apt-get install -fy python3-github python3-dotenv`).

Other than that, the tool is a simple Python script.

## Configuring the tool

The tool accepts several parameters either as
environment variables or through a file named
`.env`.  These parameters include:

### Required Variables

* **PAT**: the Personal Access Token to use when
  interfacing with the GitHub API
* **ORG**: the name of the GitHub organization to query
* **TEAM_NAME**: the name of the team to synchronize

### Optional Variables

* **DRY_RUN**: if "false", it perform the sync; otherwise, just
  display messages saying what it would do but don't actually
  perform the sync
* **API_URL**: the URL to the API to be queried; update this to
  support GitHub Enterprise (GHE) installations
* **DELAY**: the number of seconds to delay between each user operation
* **LOG_LEVEL**: the threshold for displaying log messages
  10 = Debug, 20 = Info (default), 30 = Warning, 40 = Error, 50 = Critcal
* **USER_FILTERS**: a JSON object that allows for the filtering of
  users who may be members of the team.

#### Filtering Users

The membership of the team may be limited by filters that
are applied when the team membership is synchronized.  These
filters are regular expressions that may match substrings
of various user fields.  Common fields for filtering are
`login` and `email`.  For a full list of available fields,
see the [Get a user](https://docs.github.com/en/rest/users/users?apiVersion=2022-11-28#get-a-user)
in the GitHub API documentation.

The `USER_FILTERS` variable accepts a JSON object.  At
the top level, the first element is a dictionary of which
field to examine.  Typically, this is `login` which means that
the filter will be applied to users `login` fields (i.e.,
their usernames).  Each field represents a dictionary
with zero to three fields:

* allow
* reject
* order

The `allow` and `reject` elements are lists of strings,
each of which represent a case-insensitive regular expression.

The logic for applying `USER_FILTERS` works like this:

1. if a regex under `reject` matches, the user is rejected
  from membership in the team
2. however, if a regex under `allow` matches, the user is
  allowed membership on the team
3. any user that neither matches `reject` or `allow` is
  allowed by default.

That is, the latest match wins.

Here's a sample JSON-formatted `USER_FILTERS` value:

`{"login":{"reject":["^w"],"allow":["s$"]}}`

...which is pretty-printed as:

```JSON
{
  "login": {
    "reject": [
      "^w"
    ],
    "allow": [
      "s$"
    ]
  }
}
```

In this example, the `login` (username) field is
examined.  Users with a username that starts with
a "w" (i.e., the `^w` regex under `reject`) are
removed, but the `allow` list includes a regex
that matches user with a username that ends with
"s" (i.e., the `s$` regex under `allow`).

* `sam` is allowed (doesn't match `^w`, so default allow)
* `wanda` is denied (matches `^w` but not `s$`)
* `wes` is allowed (matches `^w` but also `s$`)

Users that are determined to be "allowed" but who aren't
on the team are added to the team.

Users that are determined to be "rejected" but who are
currently on the team are removed from the team.

In addition to `allow` and `reject`, each field may
also include a field `order` which indicates the
order in which the fields are to be examined.
The default `order` is 0 with higher numbers
processed later.  (e.g., order `0` items are
processed first, then order `1`, and so on) the
orders do not need to be consecutive -- they're
only used for sorting.  Consider the following:

```JSON
{
  "login": {
    "reject": [
      "^w"
    ],
    "allow": [
      "s$"
    ]
  },
  "site_admin": {
    "allow": [
      "true"
    ],
    "order": 100
  }
}
```

In this example, the regexes for `^w` and `s$`
are processed first (the fields are processed
from lowest order to highest (default is 0) which
would reject `wesley-dean`.  However, if the
`site_admin` was `true` for `wesley-dean`, regardless
of the first field, the second field would result in
a `true` and `wesley-dean` would be allowed.  However,
if `wesley-dean-flexion` were evaluated and the
`site_admin` field was false, then `wesley-dean-flexion`
would be rejected.

### Scoping the PAT

The Personal Access Token (PAT) must have several
scopes in order to function properly:

* **read:org**: read the organization's membership
* **write:org**: update the team's membership
* **admin:org**: to create the team if it doesn't exist

The admin:org scope is only used if the tool is to
create the team in question; if the team already
exists, this scope isn't required.  Similarly, if
the tool creates the team when first run, assuming
the name of the team doesn't change, it won't require
admin access any longer.

## Running the tool

The tool is a Python script that can be invoked directly
from the command line:

```bash
python3 ./sync.py
```

### Running the tool via a schedule

The tool can be run via a cronjob, GitHub Action,
Jenkins pipeline, etc..  The only requirement is
that the enviornment should have access to the Internet
to interact with the GitHub API.
