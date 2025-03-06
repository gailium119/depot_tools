# Copyright (c) 2024 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Defines utilities for setting up Git authentication."""

from __future__ import annotations

import enum
from collections.abc import Collection
import contextlib
import functools
import logging
import os
from typing import TYPE_CHECKING, Callable, TextIO
import urllib.parse

import gerrit_util
import newauth
import scm

if TYPE_CHECKING:
    # Causes import cycle if imported normally
    import git_cl


class ConfigMode(enum.Enum):
    """Modes to pass to ConfigChanger"""
    NO_AUTH = 1
    NEW_AUTH = 2
    NEW_AUTH_SSO = 3


class ConfigChanger(object):
    """Changes Git auth config as needed for Gerrit."""

    # Can be used to determine whether this version of the config has
    # been applied to a Git repo.
    #
    # Increment this when making changes to the config, so that reliant
    # code can determine whether the config needs to be re-applied.
    VERSION: int = 5

    def __init__(
        self,
        *,
        mode: ConfigMode,
        remote_url: str,
        set_config_func: Callable[..., None] = scm.GIT.SetConfig,
    ):
        """Create a new ConfigChanger.

        Args:
            mode: How to configure auth
            remote_url: Git repository's remote URL, e.g.,
                https://chromium.googlesource.com/chromium/tools/depot_tools.git
            set_config_func: Function used to set configuration.  Used
                for testing.
        """
        self.mode: ConfigMode = mode

        self._remote_url: str = remote_url
        self._set_config_func: Callable[..., None] = set_config_func

    @functools.cached_property
    def _shortname(self) -> str:
        # Example: chromium
        parts: urllib.parse.SplitResult = urllib.parse.urlsplit(
            self._remote_url)
        return _url_shortname(parts)

    @functools.cached_property
    def _host_url(self) -> str:
        # Example: https://chromium.googlesource.com
        # Example: https://chromium-review.googlesource.com
        parts: urllib.parse.SplitResult = urllib.parse.urlsplit(
            self._remote_url)
        return _url_host_url(parts)

    @functools.cached_property
    def _root_url(self) -> str:
        # Example: https://chromium.googlesource.com/
        # Example: https://chromium-review.googlesource.com/
        parts: urllib.parse.SplitResult = urllib.parse.urlsplit(
            self._remote_url)
        return _url_root_url(parts)

    @classmethod
    def new_from_env(cls, cwd: str, cl: git_cl.Changelist) -> ConfigChanger:
        """Create a ConfigChanger by inferring from env.

        The Gerrit host is inferred from the current repo/branch.
        The user, which is used to determine the mode, is inferred using
        git-config(1) in the given `cwd`.
        """
        # This is determined either from the branch or repo config.
        #
        # Example: chromium-review.googlesource.com
        gerrit_host = cl.GetGerritHost()
        # This depends on what the user set for their remote.
        # There are a couple potential variations for the same host+repo.
        #
        # Example:
        # https://chromium.googlesource.com/chromium/tools/depot_tools.git
        remote_url = cl.GetRemoteUrl()

        if gerrit_host is None or remote_url is None:
            raise Exception(
                'Error Git auth settings inferring from environment:'
                f' {gerrit_host=} {remote_url=}')
        assert gerrit_host is not None
        assert remote_url is not None

        return cls(
            mode=cls._infer_mode(cwd, gerrit_host),
            remote_url=remote_url,
        )

    @classmethod
    def new_for_remote(cls, cwd: str, remote_url: str) -> ConfigChanger:
        """Create a ConfigChanger for the given Gerrit host.

        The user, which is used to determine the mode, is inferred using
        git-config(1) in the given `cwd`.
        """
        c = cls(
            mode=ConfigMode.NEW_AUTH,
            remote_url=remote_url,
        )
        assert c._shortname, "Short name is empty"
        c.mode = cls._infer_mode(cwd, c._shortname + '-review.googlesource.com')
        return c

    @staticmethod
    def _infer_mode(cwd: str, gerrit_host: str) -> ConfigMode:
        """Infer default mode to use."""
        if not newauth.Enabled():
            return ConfigMode.NO_AUTH
        email: str = scm.GIT.GetConfig(cwd, 'user.email') or ''
        if gerrit_util.ShouldUseSSO(gerrit_host, email):
            return ConfigMode.NEW_AUTH_SSO
        if not gerrit_util.GitCredsAuthenticator.gerrit_account_exists(
                gerrit_host):
            return ConfigMode.NO_AUTH
        return ConfigMode.NEW_AUTH

    def apply(self, cwd: str) -> None:
        """Apply config changes to the Git repo directory."""
        self._apply_cred_helper(cwd)
        self._apply_sso(cwd)
        self._apply_gitcookies(cwd)

    def apply_global(self, cwd: str) -> None:
        """Apply config changes to the global (user) Git config.

        This will make the instance's mode (e.g., SSO or not) the global
        default for the Gerrit host, if not overridden by a specific Git repo.
        """
        self._apply_global_cred_helper(cwd)
        self._apply_global_sso(cwd)

    def _apply_cred_helper(self, cwd: str) -> None:
        """Apply config changes relating to credential helper."""
        cred_key: str = f'credential.{self._host_url}.helper'
        if self.mode == ConfigMode.NEW_AUTH:
            self._set_config(cwd, cred_key, '', modify_all=True)
            self._set_config(cwd, cred_key, 'luci', append=True)
        elif self.mode == ConfigMode.NEW_AUTH_SSO:
            self._set_config(cwd, cred_key, None, modify_all=True)
        elif self.mode == ConfigMode.NO_AUTH:
            self._set_config(cwd, cred_key, None, modify_all=True)
        else:
            raise TypeError(f'Invalid mode {self.mode!r}')

        # Cleanup old from version 4
        old_key: str = f'credential.{self._root_url}.helper'
        self._set_config(cwd, old_key, None, modify_all=True)

    def _apply_sso(self, cwd: str) -> None:
        """Apply config changes relating to SSO."""
        sso_key: str = f'url.sso://{self._shortname}/.insteadOf'
        http_key: str = f'url.{self._remote_url}.insteadOf'
        if self.mode == ConfigMode.NEW_AUTH:
            self._set_config(cwd, 'protocol.sso.allow', None)
            self._set_config(cwd, sso_key, None, modify_all=True)
            # Shadow a potential global SSO rewrite rule.
            self._set_config(cwd, http_key, self._remote_url, modify_all=True)
        elif self.mode == ConfigMode.NEW_AUTH_SSO:
            self._set_config(cwd, 'protocol.sso.allow', 'always')
            self._set_config(cwd, sso_key, self._root_url, modify_all=True)
            self._set_config(cwd, http_key, None, modify_all=True)
        elif self.mode == ConfigMode.NO_AUTH:
            self._set_config(cwd, 'protocol.sso.allow', None)
            self._set_config(cwd, sso_key, None, modify_all=True)
            self._set_config(cwd, http_key, None, modify_all=True)
        else:
            raise TypeError(f'Invalid mode {self.mode!r}')

    def _apply_gitcookies(self, cwd: str) -> None:
        """Apply config changes relating to gitcookies."""
        if self.mode == ConfigMode.NEW_AUTH:
            # Override potential global setting
            self._set_config(cwd, 'http.cookieFile', '', modify_all=True)
        elif self.mode == ConfigMode.NEW_AUTH_SSO:
            # Override potential global setting
            self._set_config(cwd, 'http.cookieFile', '', modify_all=True)
        elif self.mode == ConfigMode.NO_AUTH:
            self._set_config(cwd, 'http.cookieFile', None, modify_all=True)
        else:
            raise TypeError(f'Invalid mode {self.mode!r}')

    def _apply_global_cred_helper(self, cwd: str) -> None:
        """Apply config changes relating to credential helper."""
        cred_key: str = f'credential.{self._host_url}.helper'
        if self.mode == ConfigMode.NEW_AUTH:
            self._set_config(cwd, cred_key, '', scope='global', modify_all=True)
            self._set_config(cwd, cred_key, 'luci', scope='global', append=True)
        elif self.mode == ConfigMode.NEW_AUTH_SSO:
            # Avoid editing the user's config in case they manually
            # configured something.
            pass
        elif self.mode == ConfigMode.NO_AUTH:
            # Avoid editing the user's config in case they manually
            # configured something.
            pass
        else:
            raise TypeError(f'Invalid mode {self.mode!r}')

        # Cleanup old from version 4
        old_key: str = f'credential.{self._root_url}.helper'
        self._set_config(cwd, old_key, None, modify_all=True)

    def _apply_global_sso(self, cwd: str) -> None:
        """Apply config changes relating to SSO."""
        sso_key: str = f'url.sso://{self._shortname}/.insteadOf'
        if self.mode == ConfigMode.NEW_AUTH:
            # Do not unset protocol.sso.allow because it may be used by
            # other hosts.
            self._set_config(cwd,
                             sso_key,
                             None,
                             scope='global',
                             modify_all=True)
        elif self.mode == ConfigMode.NEW_AUTH_SSO:
            self._set_config(cwd,
                             'protocol.sso.allow',
                             'always',
                             scope='global')
            self._set_config(cwd,
                             sso_key,
                             self._root_url,
                             scope='global',
                             modify_all=True)
        elif self.mode == ConfigMode.NO_AUTH:
            # Avoid editing the user's config in case they manually
            # configured something.
            pass
        else:
            raise TypeError(f'Invalid mode {self.mode!r}')

    def _set_config(self, *args, **kwargs) -> None:
        self._set_config_func(*args, **kwargs)


def AutoConfigure(cwd: str, cl: git_cl.Changelist) -> None:
    """Configure Git authentication automatically.

    This tracks when the config that has already been applied and skips
    doing anything if so.

    This may modify the global Git config and the local repo config as
    needed.
    """
    latestVer: int = ConfigChanger.VERSION
    v: int = 0
    try:
        v = int(
            scm.GIT.GetConfig(cwd, 'depot-tools.gitauthautoconfigured') or '0')
    except ValueError:
        v = 0
    if v < latestVer:
        logging.debug(
            'Automatically configuring Git repo authentication'
            ' (current version: %r, latest: %r)', v, latestVer)
        Configure(cwd, cl)
        scm.GIT.SetConfig(cwd, 'depot-tools.gitAuthAutoConfigured',
                          str(latestVer))


def Configure(cwd: str, cl: git_cl.Changelist) -> None:
    """Configure Git authentication.

    This may modify the global Git config and the local repo config as
    needed.
    """
    logging.debug('Configuring Git authentication...')

    logging.debug('Configuring global Git authentication...')

    # We want the user's global config.
    # We can probably assume the root directory doesn't have any local
    # Git configuration.
    c = ConfigChanger.new_from_env('/', cl)
    c.apply_global(os.path.expanduser('~'))

    c2 = ConfigChanger.new_from_env(cwd, cl)
    if c2.mode == c.mode:
        logging.debug(
            'Local user wants same mode %s as global;'
            ' clearing local repo auth config', c2.mode)
        c2.mode = ConfigMode.NO_AUTH
        c2.apply(cwd)
        return
    logging.debug('Local user wants mode %s while global user wants mode %s',
                  c2.mode, c.mode)
    logging.debug('Configuring current Git repo authentication...')
    c2.apply(cwd)


def ConfigureGlobal(cwd: str, remote_url: str) -> None:
    """Configure global/user Git authentication."""
    logging.debug('Configuring global Git authentication for %s', remote_url)
    if remote_url.startswith('file://'):
        return
    ConfigChanger.new_for_remote(cwd, remote_url).apply_global(cwd)


def ClearRepoConfig(cwd: str, cl: git_cl.Changelist) -> None:
    """Clear the current Git repo authentication."""
    logging.debug('Clearing current Git repo authentication...')
    c = ConfigChanger.new_from_env(cwd, cl)
    c.mode = ConfigMode.NO_AUTH
    c.apply(cwd)


class _ConfigError(Exception):
    """Subclass for errors raised by ConfigWizard."""


class ConfigWizard(object):

    def __init__(self, stdin: TextIO, stdout: TextIO):
        self._ui = _UserInterface(stdin, stdout)

    def run(self, remote_url: str):
        with self._handle_config_errors():
            if self._check_sso_helper():
                self._set_config('protocol.sso.allow', 'always', scope='global')
                self._println()
            if _is_gerrit_url(remote_url):
                self._println(
                    'Looks like we are running inside a Gerrit repository,')
                self._println(
                    f'so we will check your Git configuration for {remote_url}')
                self._println()
                parts = urllib.parse.urlsplit(remote_url)
                self._run_inside_repo(parts)
            else:
                self._println(
                    'Looks like we are running outside of a Gerrit repository,')
                self._println('so we will check your global Git configuration.')
                self._println()
                self._run_outside_repo()

    def _run_outside_repo(self) -> None:
        global_email = self._check_global_email()

        self._println()
        self._println('Since we are not running in a Gerrit repository,'
                      ' we do not know which Gerrit host(s) to check for.')
        self._println(
            'You can re-run this command inside a Gerrit repository,'
            ' or we can try to set up some commonly used Gerrit hosts.')
        if not self._ui.read_yn('Set up commonly used Gerrit hosts?',
                                default=True):
            return

        hosts = []
        if self._ui.read_yn('Do you work on chromium?', default=False):
            hosts.extend([
                'chromium.googlesource.com',
            ])
        for host in hosts:
            self._println()
            self._println(f'Checking authentication config for {host}')
            parts = urllib.parse.urlsplit(f'https://{host}/')
            self._configure(parts, global_email, scope='global')

    def _run_inside_repo(self, parts: urllib.parse.SplitResult) -> None:
        global_email = self._check_global_email()
        local_email = self._check_local_email()

        email = global_email
        scope = 'global'
        if local_email and local_email != global_email:
            self._println('You have an email configured in your local repo'
                          ' which is different than your global Git config.')
            self._println(
                'We will configure Gerrit authentication for your local repo only.'
            )
            self._println()
            email = local_email
            scope = 'local'
        self._configure(parts, email, scope=scope)

    def _configure(self, parts: urllib.parse.SplitResult, email: str, *,
                   scope: scm.GitConfigScope) -> None:
        use_sso = self._check_use_sso(parts, email)
        if use_sso:
            self._configure_sso(parts, scope=scope)
        else:
            self._configure_oauth(parts, scope=scope)

    def _configure_sso(self, parts: urllib.parse.SplitResult, *,
                       scope: scm.GitConfigScope) -> None:
        if parts.scheme == 'sso':
            self._println(f'Your remote URL {parts.geturl()} already uses SSO')
        else:
            self._set_sso_rewrite(parts, scope=scope)
        self._clear_http_rewrite(parts, scope=scope)
        self._clear_oauth_helper(parts, scope=scope)

    def _configure_oauth(self, parts: urllib.parse.SplitResult, *,
                         scope: scm.GitConfigScope) -> None:
        self._set_oauth_helper(parts, scope=scope)
        if scope == 'local':
            # Override a potential SSO rewrite set in the global config
            self._set_http_rewrite(parts, scope=scope)
        self._clear_sso_rewrite(parts, scope=scope)

    def _check_gitcookies(self):
        # Check if .gitcookies exists
        # Check creds in gitcookies
        # check git config for cookiefile
        ...  # XXXXXXXXXXXXXXXX

    def _check_global_email(self) -> str:
        email = scm.GIT.GetConfig(os.getcwd(), 'user.email',
                                  scope='global') or ''
        if email:
            self._println(f'Your global Git email is: {email}')
            return email
        self._println(
            'You do not have an email configured in your global Git config.')
        if not self._ui.read_yn('Do you want to set it up now?', default=True):
            self._println('Will attempt to continue without a global email.')
            return ''
        name = scm.GIT.GetConfig(os.getcwd(), 'user.name', scope='global') or ''
        if not name:
            name = self._ui.read_line('Enter your name (e.g., John Doe)',
                                      check=_check_nonempty)
            self._set_config('user.name', name, scope='global')
        email = self._ui.read_line('Enter your email', check=_check_nonempty)
        self._set_config('user.email', email, scope='global')
        return email

    def _check_local_email(self) -> str:
        email = scm.GIT.GetConfig(os.getcwd(), 'user.email',
                                  scope='local') or ''
        if email:
            self._println(
                f'You have an email configured in your local repo: {email}')
        return email

    def _check_use_sso(self, parts: urllib.parse.SplitResult,
                       email: str) -> bool:
        host = _url_review_host(parts)
        result = gerrit_util.CheckShouldUseSSO(host, email)
        text = 'use' if result.status else 'not use'
        self._println(
            f'Determined we should {text} SSO for {email!r} on {host}')
        self._println(f'Reason: {result.reason}')
        self._println()
        return result.status

    def _check_sso_helper(self) -> bool:
        has_sso_helper = bool(gerrit_util.ssoHelper.find_cmd())
        if has_sso_helper:
            self._println('SSO helper is available.')
        return has_sso_helper

    def _print_manual_instructions(self) -> None:
        self._println()
        self._println(
            'Follow this for instructions on manually configuring Gerrit authentication:'
        )
        self._println(
            'https://commondatastorage.googleapis.com/chrome-infra-docs/flat/depot_tools/docs/html/depot_tools_gerrit_auth.html'
        )

    def _set_oauth_helper(self, parts: urllib.parse.SplitResult, *,
                          scope: scm.GitConfigScope) -> None:
        cred_key = _creds_helper_key(parts)
        self._set_config(cred_key, '', modify_all=True, scope=scope)
        self._set_config(cred_key, 'luci', append=True, scope=scope)
        # XXXXX explain empty value

    def _clear_oauth_helper(self, parts: urllib.parse.SplitResult, *,
                            scope: scm.GitConfigScope) -> None:
        cred_key = _creds_helper_key(parts)
        self._set_config(cred_key, None, modify_all=True, scope=scope)

    def _set_sso_rewrite(self, parts: urllib.parse.SplitResult, *,
                         scope: scm.GitConfigScope) -> None:
        sso_key = _sso_rewrite_key(parts)
        self._set_config(sso_key,
                         _url_host_url(parts),
                         modify_all=True,
                         scope=scope)

    def _clear_sso_rewrite(self, parts: urllib.parse.SplitResult, *,
                           scope: scm.GitConfigScope) -> None:
        sso_key = _sso_rewrite_key(parts)
        self._set_config(sso_key, None, modify_all=True, scope=scope)

    def _set_http_rewrite(self, parts: urllib.parse.SplitResult, *,
                          scope: scm.GitConfigScope) -> None:
        http_key = _https_rewrite_key(parts)
        self._set_config(http_key,
                         _url_root_url(parts),
                         modify_all=True,
                         scope=scope)

    def _clear_http_rewrite(self, parts: urllib.parse.SplitResult, *,
                            scope: scm.GitConfigScope) -> None:
        http_key = _https_rewrite_key(parts)
        self._set_config(http_key, None, scope=scope, modify_all=True)

    def _set_config(self,
                    name: str,
                    value: str | None,
                    *,
                    scope: scm.GitConfigScope,
                    modify_all: bool = False,
                    append: bool = False) -> None:
        scope_msg = f'In your {scope} Git config,'
        if append:
            assert value is not None
            self._println(
                f'> {scope_msg} appending {name}={value!r} to existing values')
        else:
            action = f'setting {name}={value!r}'
            if value is None:
                action = f'clearing {name} values'
            tail = ''
            if modify_all:
                tail = ', replacing all existing values'
            self._println(f'> {scope_msg} {action}{tail}')

        scm.GIT.SetConfig(os.getcwd(),
                          name,
                          value,
                          scope=scope,
                          modify_all=modify_all,
                          append=append)

    @contextlib.contextmanager
    def _handle_config_errors(self):
        try:
            yield None
        except _ConfigError as e:
            self._println(f'ConfigError: {e!s}')

    def _println(self, s: str = '') -> None:
        self._ui.write(s)
        self._ui.write('\n')


_InputChecker = Callable[['_UserInterface', str], bool]


def _check_any(ui: _UserInterface, line: str) -> bool:
    """Allow any input."""
    return True


def _check_nonempty(ui: _UserInterface, line: str) -> bool:
    """Reject nonempty input."""
    if line:
        return True
    ui.write('Input cannot be empty.\n')
    return False


def _check_choice(choices: Collection[str]) -> _InputChecker:
    """Allow specified choices."""

    def func(ui: _UserInterface, line: str) -> bool:
        if line in choices:
            return True
        ui.write('Invalid choice.\n')
        return False

    return func


class _UserInterface(object):
    """Abstracts user interaction.

    This implementation supports regular terminals.
    """

    _prompts = {
        None: 'y/n',
        True: 'Y/n',
        False: 'y/N',
    }

    def __init__(self, stdin: TextIO, stdout: TextIO):
        self._stdin = stdin
        self._stdout = stdout

    def read_yn(self, prompt: str, *, default: bool | None = None) -> bool:
        """Reads a yes/no response.

        The prompt should end in '?'.
        """
        prompt = f'{prompt} [{self._prompts[default]}]: '
        while True:
            self._stdout.write(prompt)
            self._stdout.flush()
            response = self._stdin.readline().strip().lower()
            if response in ('y', 'yes'):
                return True
            if response in ('n', 'no'):
                return False
            if not response and default is not None:
                return default
            self._stdout.write('Type y or n.\n')

    def read_line(self,
                  prompt: str,
                  *,
                  check: _InputChecker = _check_any) -> str:
        """Reads a line of input.

        Trailing whitespace is stripped from the read string.
        The prompt should not end in any special indicator like a colon.

        Optionally, an input check function may be provided.  This
        method will continue to prompt for input until it passes the
        check.  The check should print some explanation for rejected
        inputs.
        """
        while True:
            self._stdout.write(f'{prompt}: ')
            self._stdout.flush()
            s = self._stdin.readline().rstrip()
            if check(self, s):
                return s

    def write(self, s: str) -> None:
        """Write string as-is.

        The string should usually end in a newline.
        """
        self._stdout.write(s)


def _is_gerrit_url(url: str) -> bool:
    """Checks if URL is for a Gerrit host."""
    if not url:
        return False
    parts = urllib.parse.urlsplit(url)
    if parts.netloc.endswith('.googlesource.com') or parts.netloc.endswith(
            '.git.corp.google.com'):
        return True
    return False


def _creds_helper_key(parts: urllib.parse.SplitResult) -> str:
    """Return Git config key for credential helpers."""
    return f'credential.{_url_host_url(parts)}.helper'


def _sso_rewrite_key(parts: urllib.parse.SplitResult) -> str:
    """Return Git config key for SSO URL rewrites."""
    return f'url.sso://{_url_shortname(parts)}/.insteadOf'


def _https_rewrite_key(parts: urllib.parse.SplitResult) -> str:
    """Return Git config key for HTTPS URL rewrites."""
    return f'url.{_url_root_url(parts)}.insteadOf'


def _url_review_host(parts: urllib.parse.SplitResult) -> str:
    """Format URL as Gerrit review host.

    Example: chromium-review.googlesource.com
    """
    return f'{_url_shortname(parts)}-review.googlesource.com'


def _url_shortname(parts: urllib.parse.SplitResult) -> str:
    """Format URL as Gerrit host shortname.

    Example: chromium
    """
    name: str = parts.netloc.split('.')[0]
    if name.endswith('-review'):
        name = name[:-len('-review')]
    return name


def _url_host_url(parts: urllib.parse.SplitResult) -> str:
    """Format URL with host only (no path).

    Example: https://chromium.googlesource.com
    Example: https://chromium-review.googlesource.com
    """
    return parts._replace(path='', query='', fragment='').geturl()


def _url_root_url(parts: urllib.parse.SplitResult) -> str:
    """Format URL with root path.

    Example: https://chromium.googlesource.com/
    Example: https://chromium-review.googlesource.com/
    """
    return parts._replace(path='/', query='', fragment='').geturl()
