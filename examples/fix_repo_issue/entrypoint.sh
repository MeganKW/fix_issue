#!/bin/bash
set -euo pipefail

pip install PyGithub requests gitpython
python fix_repo_issue.py 