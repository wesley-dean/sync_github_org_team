#!/usr/bin/env python3

import os

from github import Github
from github import Auth
from dotenv import load_dotenv

load_dotenv()

PAT = os.environ['PAT']
ORG = os.environ['ORG']
TEAM_NAME = os.environ['TEAM_NAME']

auth = Auth.Token(PAT)


current_org_members = {}
current_team_members = {}

g = Github(auth=auth)

organization = g.get_organization(ORG)
org_members = organization.get_members()
teams = organization.get_teams()

team_exists = False

for team in teams:
    if team.name == TEAM_NAME:
        the_team = team
        team_exists = True

if not team_exists:
    print(f"team {TEAM_NAME} doesn't exist so creating it")
    the_team = organization.create_team(TEAM_NAME)
else:
    print(f"team {TEAM_NAME} already exists")

team_members = the_team.get_members()

for member in team_members:
    current_team_members[member.login] = True

for member in org_members:
    current_org_members[member.login] = True


for member in current_org_members.keys():
    if not current_team_members[member]:
        print(f"{member} is in the org but not the team, so adding them")
        the_team.add_membership(member)
    else:
        print(f"{member} is in the org and in the team")

