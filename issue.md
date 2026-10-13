# `remote_url()` ignores configured SSH remote URL when a token is set, silently switching push transport to HTTPS

**Affects:** GitLab, GitHub, Gitea, Bitbucket (all four HVCS implementations)

---

## Summary

When `[tool.semantic_release.remote] url` is set to an SSH URL (e.g. a deploy-key
remote such as `git@gitlab.example.com:org/my-repo.git`) **and** a provider token is
present in the environment, `python-semantic-release` ignores the configured URL for
all push operations and constructs an HTTPS token-authenticated URL instead. There is
no warning or error. The user's deploy-key SSH configuration is silently bypassed,
causing push failures or unexpected authentication behaviour.

---

## Steps to reproduce

**`pyproject.toml`:**

```toml
[tool.semantic_release.remote]
type  = "gitlab"
url   = "git@gitlab.example.com:org/my-repo.git"   # SSH deploy-key remote
```

**Environment variable:**

```
GITLAB_TOKEN=glpat-xxxxxxxxxxxx
```

**Invocation:**

```bash
semantic-release version
```

---

## Expected behaviour

`semantic-release version` pushes the branch and tag over SSH using the configured
`git@…` remote, authenticating via the deploy key. `GITLAB_TOKEN` is used only for
GitLab API calls (creating the release, etc.).

---

## Actual behaviour

All git push operations (branch push, release-tag push, partial-tag pushes) and the
upstream-changed fetch are performed against:

```
https://gitlab-ci-token:<token>@gitlab.example.com/org/my-repo.git
```

The SSH remote URL from `pyproject.toml` is never used for push.

**Root cause — `src/semantic_release/hvcs/gitlab.py` (lines 221–229):**

```python
def remote_url(self, use_token: bool = True) -> str:
    if not (self.token and use_token):
        return self._remote_url          # SSH URL correctly returned here

    return self.create_server_url(       # self._remote_url silently discarded
        auth=f"gitlab-ci-token:{self.token}",
        path=f"{self.project_namespace}.git",
    )
```

`create_server_url()` builds on `self._hvcs_domain` (always HTTPS), so it produces an
HTTPS URL regardless of the scheme stored in `self._remote_url`. The identical pattern
exists in `github.py`, `gitea.py`, and `bitbucket.py`.

---

## Affected operations

A single `remote_url()` call in `src/semantic_release/cli/commands/version.py` (line
744) feeds all of:

| Operation | Location (version.py) |
|---|---|
| Upstream-unchanged fetch | line 756 |
| Branch push | line 782 |
| Release-tag push | line 790 |
| Partial-tag pushes (major, minor) | line 810 |

---

## Proposed fix

Add a scheme check in `remote_url()` before constructing the HTTPS token URL.
`parse_git_url` (already used elsewhere in the codebase) normalises SCP-style SSH
(`git@host:org/repo.git`) to `scheme="ssh"`.

```diff
# gitlab.py
-from semantic_release.helpers import logged_function
+from semantic_release.helpers import logged_function, parse_git_url

 def remote_url(self, use_token: bool = True) -> str:
     if not (self.token and use_token):
         return self._remote_url

+    # Honour the configured URL when it uses a non-HTTP/S scheme (e.g. SSH).
+    if parse_git_url(self._remote_url).scheme not in ("http", "https"):
+        return self._remote_url
+
     return self.create_server_url(
         auth=f"gitlab-ci-token:{self.token}",
         path=f"{self.project_namespace}.git",
     )
```

The same one-line guard must be applied to the equivalent location in `github.py`,
`gitea.py`, and `bitbucket.py`.

For Bitbucket specifically, the guard should be placed **before** the
`raise ValueError("Requested to use token but no token set.")` check, so that users
with an SSH URL do not need a token configured at all (consistent with the behaviour
of the other three providers).

---

## Workaround

Until a patched release is available, add `ignore_token_for_push = true` under
`[tool.semantic_release.remote]`:

```toml
[tool.semantic_release.remote]
type = "gitlab"
ignore_token_for_push = true
```

This causes PSR to call `remote_url(use_token=False)`, which returns `self._remote_url`
directly. The side-effect is that any HTTPS-insteadOf rewriting you may rely on is also
disabled, but for pure SSH deploy-key setups this is the correct behaviour.
