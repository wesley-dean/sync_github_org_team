#!/usr/bin/env python

"""
@file sync
@brief Synchronize a GitHub organization's membership to a Team
@details
GitHub does not create a team that automatically includes all of
the organization's members.  Because collaborators are either
individuals or teams but not organizations, there is no native
way to grant all members of an organization access to, for example,
an internal repository.

Therefore, this script will create and populate a team in an
organization that has as its membership the members of the
organization.  This allows folks to provide access to a team
that represents everyone in the organization.  For example:

    @my-organization/everyone
"""

import logging
import os

from dotenv import load_dotenv
from github import Github

logging.basicConfig(level=logging.DEBUG)

load_dotenv()

PAT = str(os.getenv("PAT"))
ORG = str(os.environ["ORG"])

TEAM_NAME = os.environ["TEAM_NAME"]
DRY_RUN = os.getenv("DRY_RUN", "True")
API_URL = os.getenv("API_URL", "https://api.github.com")


def create_team_if_not_exists(team_name, organization):
    """
    @fn create_team_if_not_exists()
    @brief if a team doesn't exist, create it; either way, return it
    @details
    Given an organization and the name of a team, check to see if a
    team with that name exists in the organization.  If it exists,
    return a team object immediately; if it does not exist, create
    the team (requires admin:org scope) and then return a team object
    @param team_name the name of the team (just the name, not the org)
    @param organization the organization object
    @returns team object
    @par Example
    @code
    my_team = create_team_if_not_exists("my_team", my_org)
    @endcode
    """

    logging.debug("Fetching teams from organization")
    teams = organization.get_teams()

    for team in teams:
        logging.debug(
            'Comparing requested "%s" with detected "%s"', team_name, team.name
        )
        if team.name == team_name:
            logging.debug("Found a match")
            return team

    logging.info('Team "%s" was not found; creating it.', team_name)
    return organization.create_team(team_name)


def get_group_logins(group):
    """
    @fn get_group_logins()
    @brief given a team or an organization, return a dict of its members
    @details
    This will iterate through the list of members in either a team or
    an organization and return a dict with each member's login as the
    key and True as the value.
    @param group the team or organization object to query
    @returns dict with the members' logins as keys
    @par Examples
    @code
    team_members = get_group_logins(team)
    org_members = get_group_logins(organization)
    @endcode
    """

    member_logins = {}

    for member in group.get_members():
        logging.debug('Found member "%s"', member.login)
        member_logins[member.login] = True

    return member_logins


def main():
    """
    @fn main()
    @brief the main function
    """

    logging.debug('Using PAT "%s**************************"', PAT[1:8])
    logging.debug('Using ORG "%s"', ORG)
    logging.debug('Using TEAM_NAME "%s"', TEAM_NAME)

    github = Github(login_or_token=PAT, base_url=API_URL)

    organization = github.get_organization(ORG)

    team = create_team_if_not_exists(TEAM_NAME, organization)

    current_org_members = get_group_logins(organization)
    current_team_members = get_group_logins(team)

    for member in current_org_members:
        if not current_team_members[member]:
            logging.info('"%s" is in the org but not the team, so adding them', member)
            if not DRY_RUN.lower == "false":
                team.add_membership(member)
        else:
            logging.debug('"%s" is in the org and in the team', member)


if __name__ == "__main__":
    main()
