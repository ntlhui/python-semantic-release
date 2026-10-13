"""
Minimal Working Example — SSH remote URL ignored when token is present

Demonstrates the bug (and fix) in python-semantic-release where configuring an SSH
remote URL is silently overridden with an HTTPS token URL when a provider token is
set.  Affects all four HVCS implementations: GitLab, GitHub, Gitea, Bitbucket.

Run with the project's venv:
    .venv/bin/python mwe_ssh_remote_url_bug.py

Expected output after the fix is applied:
    [PASS] GitLab:    git@gitlab.com:org/repo.git
    [PASS] GitHub:    git@github.com:org/repo.git
    [PASS] Gitea:     git@gitea.com:org/repo.git
    [PASS] Bitbucket: git@bitbucket.org:org/repo.git
"""

from __future__ import annotations

import os
import sys
from unittest import mock

with mock.patch.dict(os.environ, {}, clear=True):
    from semantic_release.hvcs.bitbucket import Bitbucket
    from semantic_release.hvcs.gitea import Gitea
    from semantic_release.hvcs.github import Github
    from semantic_release.hvcs.gitlab import Gitlab

TOKEN = "dummy-token-abc123"

CASES: list[tuple[str, object, str]] = [
    ("GitLab",    Gitlab,    f"git@{Gitlab.DEFAULT_DOMAIN}:org/repo.git"),
    ("GitHub",    Github,    f"git@{Github.DEFAULT_DOMAIN}:org/repo.git"),
    ("Gitea",     Gitea,     f"git@{Gitea.DEFAULT_DOMAIN}:org/repo.git"),
    ("Bitbucket", Bitbucket, f"git@{Bitbucket.DEFAULT_DOMAIN}:org/repo.git"),
]

failures = 0

for label, cls, ssh_url in CASES:
    with mock.patch.dict(os.environ, {}, clear=True):
        client = cls(remote_url=ssh_url, token=TOKEN)
    result = client.remote_url(use_token=True)
    if result == ssh_url:
        print(f"[PASS] {label:<10} {result}")
    else:
        print(f"[FAIL] {label:<10} expected: {ssh_url}")
        print(f"              got:      {result}")
        failures += 1

sys.exit(failures)
