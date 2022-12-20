import argparse
import os
import re
import subprocess
import shutil
import json

from pathlib import Path
import sys
from typing import Any, Dict, List, Literal, TypedDict

from codeplag.consts import UTIL_NAME
from codeplag.consts import EXTENSION_CHOICE
from webparsers.github_parser import GitHubParser


class PullCheckReport(TypedDict):
    branch: str
    status: Literal["passed", "failed"]
    info: List[Dict[str, Any]]


PullsReport = Dict[int, PullCheckReport]

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", '')
REPORTS_DIRECTORY = Path('/usr/src/reports')
WORKS_DIRECTORY = Path('/usr/src/works')
PULL_REQ_TEMPL = "https://github.com/{owner}/{repo}/tree/{branch}/{branch}/"


def run_util(cmd_seq: List[str], opts: Dict[str, Any]) -> subprocess.CompletedProcess:
    cmd_str = " ".join(cmd_seq)
    options_str = " ".join(
        f'--{opt} {" ".join(value) if type(value) == list else value}' for opt, value in opts.items()
    )

    return subprocess.run(
        f'{UTIL_NAME} {cmd_str} {options_str}',
        shell=True
    )


if __name__ == '__main__':
    compl_proc = subprocess.run(
        'git config --get remote.origin.url',
        shell=True,
        text=True,
        stdout=subprocess.PIPE
    )
    match = re.search(r":(?P<owner>\w+)/(?P<repo>\w+)[.]git$", compl_proc.stdout)
    if not match:
        print("ERROR: current path is not a git repository.", file=sys.stderr)
        exit(1)

    owner = match.group('owner')
    repo = match.group('repo')

    parser = GitHubParser(access_token=ACCESS_TOKEN)
    pulls = parser.get_pulls_info(owner, repo)

    work_links = []
    pulls_report: PullsReport = {}
    for pull in pulls:
        work_links.append(
            PULL_REQ_TEMPL.format(owner=owner, repo=repo, branch=pull.branch)
        )
        pulls_report[pull.number] = {
            'branch': pull.branch,
            'status': 'passed',
            'info': []
        }

    shutil.rmtree(REPORTS_DIRECTORY, ignore_errors=True)
    REPORTS_DIRECTORY.mkdir(exist_ok=True)
    run_util(
        cmd_seq=['settings', 'modify'],
        opts={'reports': REPORTS_DIRECTORY}
    )

    for extensin in EXTENSION_CHOICE:
        run_util(
            cmd_seq=['check'],
            opts={
                'extension': extensin,
                'mode': 'one_to_one',
                'directories': WORKS_DIRECTORY,
                'github-project-folders': work_links
            }
        )

    for filename in REPORTS_DIRECTORY.iterdir():
        report = json.loads(filename.read_text())
        for pull_report in pulls_report.values():
            if re.compile(pull_report['branch']).search(report["first_path"]):
                pull_report['info'].append(report)
                pull_report['status'] = 'failed'
            elif re.compile(pull_report['branch']).search(report["second_path"]):
                pull_report['info'].append(report)
                pull_report['status'] = 'failed'

    with open(REPORTS_DIRECTORY / "main.json", "w") as f:
        json.dump(pulls_report, f)
