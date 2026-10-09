"""Keep credentials out of hook environments, command echoes and error messages.

Modelled on GitPython's ``remove_password_if_present``, but secrets here are usually
embedded inside a larger argument (``--env APPS=[{"repo_url": "https://<token>@..."}]``,
``--env GITHUB_TOKEN=...``) rather than being a whole URL argument, so they are matched
anywhere in the text.
"""

import re
from typing import Any, Iterable

REDACTED = "*****"

# Config keys / env var names whose values are credentials.
_SECRET_NAME = re.compile(r"token|secret|passw(?:or)?d|(?:^|_|api)key$", re.IGNORECASE)

# scheme://user[:password]@ e.g. https://<token>@github.com/org/repo
_URL_USERINFO = re.compile(r"\b(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?P<user>[^\s/:@'\"]*)(?::[^\s/@'\"]*)?@")

# "name": "value" (JSON-serialised config)
_JSON_PAIR = re.compile(r"\"(?P<name>[^\"]+)\"(?P<sep>\s*:\s*)\"[^\"]*\"")

# NAME=value (--env GITHUB_TOKEN=..., ?access_token=...)
_ASSIGNMENT = re.compile(r"\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?:\"[^\"]*\"|'[^']*'|[^\s'\";&|]*)")

# GitHub token formats, wherever they show up (e.g. echoed by a failing hook)
_GITHUB_TOKEN = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")


def is_secret_name(name: str) -> bool:
    return bool(_SECRET_NAME.search(name))


def _mask_inline_secrets(text: str) -> str:
    text = _JSON_PAIR.sub(lambda m: f'"{m["name"]}"{m["sep"]}"{REDACTED}"' if is_secret_name(m["name"]) else m[0], text)
    text = _ASSIGNMENT.sub(lambda m: f"{m['name']}={REDACTED}" if is_secret_name(m["name"]) else m[0], text)
    return _GITHUB_TOKEN.sub(REDACTED, text)


def redact(text: str) -> str:
    """Mask credentials in text that is about to be printed, logged or raised."""
    text = _URL_USERINFO.sub(lambda m: f"{m['scheme']}://{REDACTED}@", text)
    return _mask_inline_secrets(text)


def redact_command(command: Iterable[Any]) -> list[str]:
    return [redact(str(part)) for part in command]


def _strip_userinfo(match: re.Match) -> str:
    scheme, user = match["scheme"], match["user"]
    # For http(s) the username slot is where tokens go (https://<token>@github.com);
    # for ssh and friends it is a login name such as git@ and only a password is secret.
    if not user or scheme.lower().rsplit("+", 1)[-1] in ("http", "https"):
        return f"{scheme}://"
    return f"{scheme}://{user}@"


def strip_url_credentials(text: str) -> str:
    return _URL_USERINFO.sub(_strip_userinfo, text)


def scrub_secrets(data: Any) -> Any:
    """Copy of config data that is safe to hand to a hook as env: secret keys dropped,
    URL credentials stripped and inline tokens masked."""
    if isinstance(data, dict):
        return {key: scrub_secrets(value) for key, value in data.items() if not is_secret_name(str(key))}
    if isinstance(data, list):
        return [scrub_secrets(item) for item in data]
    if isinstance(data, str):
        return _mask_inline_secrets(strip_url_credentials(data))
    return data
