import argparse
import os
import re
import subprocess
import shutil
import json

from pathlib import Path
from typing import Any, Dict, List, Literal, TypedDict

from codeplag.consts import UTIL_NAME
from webparsers.github_parser import GitHubParser


class PullCheckReport(TypedDict):
    branch: str
    status: Literal["passed", "failed"]
    info: List[Dict[str, Any]]


PullsReport = Dict[int, PullCheckReport]

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", '')
REPORTS_DIRECTORY = Path('/usr/src/reports')
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
    parser = argparse.ArgumentParser("check_plag")
    parser.add_argument("--owner", required=True, type=str)
    parser.add_argument("--repo", required=True, type=str)

    arguments = vars(parser.parse_args())
    owner = arguments.pop('owner')
    repo = arguments.pop('repo')

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

    REPORTS_DIRECTORY.mkdir(exist_ok=True)
    run_util(
        cmd_seq=['settings', 'modify'],
        opts={'reports': REPORTS_DIRECTORY}
    )
    run_util(
        cmd_seq=['check'],
        opts={
            'extension': 'py',
            'mode': 'one_to_one',
            'directories': '/usr/src/works/',
            'github-project-folders': work_links
        }
    )

    for filename in os.listdir(REPORTS_DIRECTORY):
        current_filepath = REPORTS_DIRECTORY / filename
        report = json.loads(current_filepath.read_text())
        for pull_report in pulls_report.values():
            if re.compile(pull_report['branch']).search(report["first_path"]):
                pull_report['info'].append(report)
                pull_report['status'] = 'failed'
            elif re.compile(pull_report['branch']).search(report["second_path"]):
                pull_report['info'].append(report)
                pull_report['status'] = 'failed'

    with open(REPORTS_DIRECTORY / "main.json", "w") as f:
        json.dump(pulls_report, f)

    shutil.rmtree(REPORTS_DIRECTORY, ignore_errors=True)
