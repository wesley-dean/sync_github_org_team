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

* **PAT**: the Personal Access Token to use when
  interfacing with the GitHub API
* **ORG**: the name of the GitHub organization to query
* **TEAM_NAME**: the name of the team to synchronize

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
