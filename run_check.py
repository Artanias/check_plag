import argparse
import os
import re
import subprocess
import shutil
import json

from pathlib import Path
from typing import Any, Dict, List

from webparsers.github_parser import GitHubParser


ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", '')
REPORTS_DIRECTORY = Path('./reports')


def run_util(cmd_seq: List[str], opts: Dict[str, Any]) -> subprocess.CompletedProcess:
    cmd_str = " ".join(cmd_seq)
    options_str = " ".join(
        f'--{opt} {" ".join(value) if type(value) == list else value}' for opt, value in opts.items()
    )

    return subprocess.run(
        f'codeplag {cmd_str} {options_str}',
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
    suspect_reports = {}
    for pull in pulls:
        work_links.append(f"https://github.com/{owner}/{repo}/tree/{pull.branch}/{pull.branch}/")
        suspect_reports[pull.branch] = []

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
            'directories': './',
            'github-project-folders': work_links
        }
    )

    for filename in os.listdir(REPORTS_DIRECTORY):
        current_filepath = REPORTS_DIRECTORY / filename
        report = json.loads(current_filepath.read_text())
        for branch_name in suspect_reports:
            if re.compile(branch_name).search(report["first_path"]):
                suspect_reports[branch_name].append(report)
            elif re.compile(branch_name).search(report["second_path"]):
                suspect_reports[branch_name].append(report)

    print(json.dumps(suspect_reports, indent=4))
    shutil.rmtree(REPORTS_DIRECTORY, ignore_errors=True)
