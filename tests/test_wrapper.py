"""OpenCode-specific launcher checks: the real entry script with OpenCode's agent part.

The launcher behavior is tested once, for every wrapper, by the shared
tests/test_launcher.py against fixture agent parts. These cases cover what only
OpenCode's own profile and agent part show: the hooks (help, provider variable
sets, native variables, integrations, YOLO), the fixed XDG bases and restricted
switches, and the provider key that follows the selected policy profile.
"""
import itertools
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'opencode-container.sh'
FAKE = (ROOT / 'tests/fake_podman.py').read_text()
sys.path.insert(0, str(ROOT / 'tests'))
from test_launcher import build_inputs_hash, synthetic_install  # noqa: E402

EXEC = '/usr/local/bin/opencode'
RELAY = ['/usr/bin/python3', '-I', '/opt/sandbox-egress/relay.py']
LABEL_HASH = build_inputs_hash(ROOT)
BYPASS = 'OPENCODE_PERMISSION={"*":"allow"}'
TRUE = ('1', 'true', 'TrUe', 'yes', 'YES')
FALSE = ('', '0', 'false', 'FaLsE', 'no', 'nO')
KEYS = {'anthropic-api': 'ANTHROPIC_API_KEY', 'openai-api': 'OPENAI_API_KEY',
        'openrouter-api': 'OPENROUTER_API_KEY', 'opencode-zen': 'OPENCODE_API_KEY'}
HOSTS = {'anthropic-api': 'api.anthropic.com', 'openai-api': 'api.openai.com',
         'openrouter-api': 'openrouter.ai', 'opencode-zen': 'opencode.ai'}
PROVIDERS = {
    'anthropic': ['ANTHROPIC_API_KEY'],
    'openai': ['OPENAI_API_KEY', 'OPENAI_BASE_URL'],
    'google': ['GOOGLE_API_KEY', 'GOOGLE_GENERATIVE_AI_API_KEY', 'GEMINI_API_KEY'],
    'openrouter': ['OPENROUTER_API_KEY'],
    'amazon-bedrock': ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_SESSION_TOKEN', 'AWS_REGION',
                       'AWS_BEARER_TOKEN_BEDROCK'],
    'azure': ['AZURE_RESOURCE_NAME', 'AZURE_API_KEY'],
    'opencode': ['OPENCODE_API_KEY'],
    'none': [],
}
ALL_PROVIDER_NAMES = sorted({name for names in PROVIDERS.values() for name in names} | {'GH_TOKEN', 'GITHUB_TOKEN'})
NATIVE = ('OPENCODE_CONFIG', 'OPENCODE_CONFIG_DIR', 'OPENCODE_CONFIG_CONTENT', 'OPENCODE_PERMISSION',
          'OPENCODE_SERVER_USERNAME', 'OPENCODE_SERVER_PASSWORD')
SWITCHES = ('OPENCODE_DISABLE_AUTOUPDATE', 'OPENCODE_DISABLE_DEFAULT_PLUGINS', 'OPENCODE_DISABLE_LSP_DOWNLOAD',
            'OPENCODE_DISABLE_MODELS_FETCH')
RESTRICTED = tuple(name + '=1' for name in SWITCHES + ('OPENCODE_DISABLE_SHARE',))
XDG = ('XDG_CONFIG_HOME=/opencode-home/.config', 'XDG_DATA_HOME=/opencode-home/.local/share',
       'XDG_CACHE_HOME=/opencode-home/.cache', 'XDG_STATE_HOME=/opencode-home/.local/state')


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='opencode-agent-', dir=os.environ.get('SANDBOX_TEST_TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        podman = self.bin / 'podman'
        podman.write_text(FAKE)
        podman.chmod(0o755)
        self.project = self.base / 'parent with spaces' / 'my project'
        self.project.mkdir(parents=True)
        self.log = self.base / 'calls.jsonl'
        self.home = self.base / 'host-home'
        self.home.mkdir()
        self.library = self.home / '.local/share/sandbox-toolchains'
        self.env = {'PATH': str(self.bin) + ':' + os.environ['PATH'], 'HOME': str(self.home),
                    'OPENCODE_CONTAINER_NETWORK': 'unrestricted', 'OPENCODE_CONTAINER_MAINTENANCE': '1',
                    'FAKE_LABEL_HASH': LABEL_HASH, 'FAKE_LOG': str(self.log)}
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket_path = self.base / 'podman.sock'
        self.socket.bind(str(self.socket_path))
        self.addCleanup(self.socket.close)
        self.env['OPENCODE_CONTAINER_PODMAN_SOCKET'] = str(self.socket_path)

    def run_wrapper(self, *args, wrapper=WRAPPER, **env):
        self.log.unlink(missing_ok=True)
        return subprocess.run([str(wrapper), *args], cwd=self.project, env=self.env | env, input='input payload',
                              text=True, capture_output=True, timeout=30)

    def calls(self):
        return [json.loads(s) for s in self.log.read_text().splitlines()] if self.log.exists() else []

    def engine_calls(self):
        return [c for c in self.calls() if not c[0].endswith('.py')]

    def agent_create(self):
        return next(c for c in self.calls() if c[0] == 'create' and not any('.egress=' in a for a in c))

    @staticmethod
    def environment(create):
        return [create[i + 1] for i, arg in enumerate(create) if arg == '--env']

    @staticmethod
    def options(create, flag):
        return [create[i + 1] for i, arg in enumerate(create) if arg == flag]

    @staticmethod
    def stable(create):
        """The engine arguments without per-session values and without the bypass setting."""
        out = [a for a in create if '.cid' not in a and '.session=' not in a]
        while BYPASS in out:
            i = out.index(BYPASS)
            del out[i - 1:i + 1]
        return out

    def toolchain_index(self, entries):
        sys.path.insert(0, str(ROOT / 'setup'))
        import toolchains
        base = toolchains.base_reference(ROOT)
        self.library.mkdir(parents=True, mode=0o700, exist_ok=True)
        entry = {'version': '1', 'default': True, 'commands': ['tool'], 'requires': [], 'notes': [],
                 'check': ['tool'], 'source': {}, 'verified': {'base': base, 'date': '2026-11-14'}}
        (self.library / 'index.json').write_text(json.dumps(
            {'schema': 1, 'toolchains': [{**entry, **value} for value in entries]}))

    def run_fresh(self, **env):
        """A launch with an empty home, to show that a refusal creates no state."""
        home = Path(tempfile.mkdtemp(dir=self.base))
        result = self.run_wrapper(HOME=str(home), **env)
        self.assertEqual(list(home.iterdir()), [])
        return result

    def assert_refused_before_engine(self, result, *texts):
        self.assertEqual(result.returncode, 1, result.stderr)
        for text in texts:
            self.assertIn(text, result.stderr)
        self.assertEqual(self.engine_calls(), [])

    def test_help_documents_the_agent_variables_and_the_provider_hosts(self):
        result = subprocess.run(['/bin/bash', str(WRAPPER), '--container-help'], cwd=self.project,
                                env={'PATH': '/usr/bin:/bin', 'HOME': str(self.home)},
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ('OPENCODE_CONTAINER_YOLO', 'OPENCODE_CONTAINER_PROVIDER', 'amazon-bedrock', 'azure',
                     'OPENCODE_CONTAINER_AGENTS_DIR', 'OPENCODE_CONTAINER_SYSTEM_CONFIG', *KEYS.values(),
                     'OPENCODE_DISABLE_AUTOUPDATE', *(f'{p}: {h}' for p, h in HOSTS.items())):
            self.assertIn(text, result.stdout)
        self.assertLess(result.stdout.index('OPENCODE_CONTAINER_NETWORK'), result.stdout.index('OPENCODE_CONTAINER_YOLO'))
        self.assertFalse(self.log.exists())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_fixed_xdg_bases_and_unrestricted_layout(self):
        # Host XDG bases elsewhere (the data base also moves the default toolchain library).
        result = self.run_wrapper('run', 'x', XDG_CONFIG_HOME='/srv/config', XDG_DATA_HOME=str(self.base / 'srv-data'),
                                  OPENCODE_CONTAINER_ENV_VARS='XDG_DATA_HOME')
        self.assertEqual(result.returncode, 0, result.stderr)
        create = self.agent_create()
        environment = self.environment(create)
        for setting in XDG:
            name = setting.split('=')[0]
            self.assertEqual([e for e in environment if e == name or e.startswith(name + '=')], [setting])
        self.assertIn('skipping XDG_DATA_HOME', result.stderr)
        volumes = self.options(create, '--volume')
        for relative in ('.config/opencode', '.local/share/opencode', '.cache/opencode', '.local/state/opencode'):
            self.assertIn(f'{self.home / relative}:/opencode-home/{relative}:rw', volumes)
        self.assertFalse(any(v.startswith('/srv') or 'srv-data/opencode' in v for v in volumes))
        self.assertIn('/opencode-home:rw,nosuid,nodev,exec,size=512m,mode=1777', self.options(create, '--tmpfs'))
        self.assertIn('/tmp:rw,nosuid,nodev,exec,size=512m,mode=1777', self.options(create, '--tmpfs'))
        self.assertFalse(any('.claude' in a for a in create))
        self.assertEqual(self.command(create), ['run', 'x'])

    @staticmethod
    def command(create):
        """Everything after the image: the entrypoint's arguments."""
        return create[next(i for i, a in enumerate(create) if a.startswith('localhost/opencode-cli')) + 1:]

    def test_provider_variable_sets_in_unrestricted_mode(self):
        values = {name: 'host-' + name for name in ALL_PROVIDER_NAMES}
        for provider, names in PROVIDERS.items():
            with self.subTest(provider=provider):
                result = self.run_wrapper(OPENCODE_CONTAINER_PROVIDER=provider, **values)
                self.assertEqual(result.returncode, 0, result.stderr)
                create = self.agent_create()
                self.assertEqual(sorted(e for e in self.environment(create) if e in ALL_PROVIDER_NAMES), sorted(names))
                self.assertFalse(any(value in ' '.join(create) for value in values.values()))
        result = self.run_wrapper(**values)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([e for e in self.environment(self.agent_create()) if e in ALL_PROVIDER_NAMES], [])
        self.assertNotIn('not forwarding', result.stderr)
        for value in ('', 'Anthropic', 'gemini', 'none '):
            with self.subTest(invalid=value):
                result = self.run_fresh(OPENCODE_CONTAINER_PROVIDER=value)
                self.assert_refused_before_engine(result, 'OPENCODE_CONTAINER_PROVIDER must be one of')

    def test_native_variables_by_name(self):
        values = {name: 'host-' + name for name in NATIVE + SWITCHES}
        values['OPENCODE_PERMISSION'] = '{"bash":"ask"}'
        result = self.run_wrapper(**values)
        self.assertEqual(result.returncode, 0, result.stderr)
        create = self.agent_create()
        environment = self.environment(create)
        for name in NATIVE + SWITCHES:
            self.assertIn(name, environment)
        self.assertFalse(any(value in ' '.join(create) for value in values.values()))

    def test_integrations_require_exact_opt_in(self):
        (self.home / '.agents').mkdir()
        system = self.base / 'etc-opencode'
        system.mkdir()
        for value in (None, 'true', 'yes', '', '0', '01'):
            with self.subTest(value=value):
                env = {} if value is None else {'OPENCODE_CONTAINER_AGENTS_DIR': value}
                result = self.run_wrapper(**env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(any('.agents' in a for a in self.options(self.agent_create(), '--volume')))
        link = self.base / 'agents-link'
        (self.home / '.agents').rename(self.base / 'agents-real')
        link.symlink_to(self.base / 'agents-real')
        (self.home / '.agents').symlink_to(link)
        result = self.run_wrapper(OPENCODE_CONTAINER_AGENTS_DIR='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'{self.base / "agents-real"}:/opencode-home/.agents:ro',
                      self.options(self.agent_create(), '--volume'))
        result = self.run_wrapper(OPENCODE_CONTAINER_SYSTEM_CONFIG='1')
        if Path('/etc/opencode').is_dir():
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(f'{Path("/etc/opencode").resolve()}:/etc/opencode:ro',
                          self.options(self.agent_create(), '--volume'))
        else:
            self.assert_refused_before_engine(result, 'OPENCODE_CONTAINER_SYSTEM_CONFIG=1', '/etc/opencode')

    def test_missing_integration_stops_before_engine(self):
        result = self.run_fresh(OPENCODE_CONTAINER_AGENTS_DIR='1')
        self.assert_refused_before_engine(result, 'OPENCODE_CONTAINER_AGENTS_DIR=1', '/.agents')
        (self.home / '.agents').write_text('not a directory')
        result = self.run_wrapper(OPENCODE_CONTAINER_AGENTS_DIR='1')
        self.assert_refused_before_engine(result, 'OPENCODE_CONTAINER_AGENTS_DIR=1')

    def test_yolo_sets_the_permission_outside_shell_mode(self):
        self.assertEqual(self.run_wrapper('run', 'x').returncode, 0)
        baseline = self.stable(self.agent_create())
        for shell, value in itertools.product((False, True), TRUE + FALSE):
            with self.subTest(shell=shell, value=value):
                options = ['--container-shell'] if shell else []
                result = self.run_wrapper(*options, 'run', 'x', OPENCODE_CONTAINER_YOLO=value)
                self.assertEqual(result.returncode, 0, result.stderr)
                create = self.agent_create()
                self.assertEqual(BYPASS in create, value in TRUE and not shell)
                if not shell:
                    self.assertEqual(self.stable(create), baseline)
        result = self.run_wrapper('--container-shell', OPENCODE_CONTAINER_YOLO='1', OPENCODE_PERMISSION='{}')
        self.assertEqual(result.returncode, 0, result.stderr)
        for value in ('maybe', ' true '):
            with self.subTest(invalid=value):
                result = self.run_fresh(OPENCODE_CONTAINER_YOLO=value)
                self.assert_refused_before_engine(result, 'OPENCODE_CONTAINER_YOLO')
        result = self.run_fresh(OPENCODE_CONTAINER_YOLO='1', OPENCODE_PERMISSION='{"*":"ask"}')
        self.assert_refused_before_engine(result, 'cannot be combined with OPENCODE_PERMISSION')

    def test_unrestricted_credentials_only_by_name(self):
        keys = {name: 'host-' + name for name in KEYS.values()}
        result = self.run_wrapper(**keys)
        self.assertEqual(result.returncode, 0, result.stderr)
        environment = self.environment(self.agent_create())
        for name in KEYS.values():
            self.assertNotIn(name, environment)
        for setting in RESTRICTED:
            self.assertNotIn(setting, environment)
        result = self.run_wrapper(OPENCODE_CONTAINER_ENV_VARS='OPENAI_API_KEY', **keys)
        self.assertEqual(result.returncode, 0, result.stderr)
        create = self.agent_create()
        self.assertEqual([e for e in self.environment(create) if e in KEYS.values()], ['OPENAI_API_KEY'])
        self.assertFalse(any(value in ' '.join(create) for value in keys.values()))


class RestrictedTests(WrapperTests):
    """Offline and provider sessions through a synthetic installation (argument instrumentation only)."""
    def setUp(self):
        super().setUp()
        self.wrapper = synthetic_install(self.base, ROOT, WRAPPER.name)
        self.policy = self.wrapper.parent / 'agent/policies/default.json'
        self.policy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'agent/policies/default.json', self.policy)
        self.runtime = self.base / 'runtime'
        self.runtime.mkdir(mode=0o700)
        self.keys = {name: 'host-' + name for name in KEYS.values()}
        self.restricted = {'OPENCODE_CONTAINER_PODMAN': '', 'FAKE_NETWORK': '1', 'FAKE_INFO': 'true linux true',
                           'CONTAINER_HOST': 'unix:///run/service.sock', **self.keys}

    def run_offline(self, *args, **env):
        return self.run_wrapper(*args, wrapper=self.wrapper, OPENCODE_CONTAINER_NETWORK='offline',
                                **(self.restricted | env))

    def run_provider(self, *args, profile='anthropic-api', **env):
        return self.run_wrapper(*args, wrapper=self.wrapper, OPENCODE_CONTAINER_NETWORK='provider',
                                OPENCODE_CONTAINER_NETWORK_PROFILE=profile,
                                OPENCODE_CONTAINER_NETWORK_POLICY=str(self.policy),
                                OPENCODE_CONTAINER_NETWORK_RUNTIME_DIR=str(self.runtime),
                                OPENCODE_CONTAINER_EGRESS_IMAGE='sha256:' + 'e' * 64, **(self.restricted | env))

    def tail(self, create):
        """The application after the guard's mode separator and, in provider mode, the relay."""
        command = create[create.index('--') + 1:]
        return command[len(RELAY):] if command[:len(RELAY)] == RELAY else command

    def test_restricted_application_settings_and_native_variables(self):
        native = {name: 'host-' + name for name in NATIVE + SWITCHES}
        for run in (self.run_offline, self.run_provider):
            with self.subTest(mode=run.__name__):
                result = run('run', 'hello world', '', **native)
                self.assertEqual(result.returncode, 0, result.stderr)
                create = self.agent_create()
                self.assertEqual(self.tail(create), [EXEC, 'run', 'hello world', ''])
                environment = self.environment(create)
                for setting in RESTRICTED + XDG:
                    name = setting.split('=')[0]
                    self.assertEqual([e for e in environment if e == name or e.startswith(name + '=')], [setting])
                for name in NATIVE:
                    self.assertIn(name, environment)
                self.assertFalse(any(value in ' '.join(create) for value in native.values()))

    def test_restricted_switches_win_over_toolchain_and_forwarded_variables(self):
        self.toolchain_index([{'name': 'noisy', 'path': ['/toolchains/noisy/bin'],
                               'env': {'OPENCODE_DISABLE_AUTOUPDATE': '0'}}])
        for run in (self.run_offline, self.run_provider):
            with self.subTest(mode=run.__name__):
                result = run(OPENCODE_DISABLE_SHARE='0',
                             OPENCODE_CONTAINER_ENV_VARS='OPENCODE_DISABLE_SHARE OPENCODE_DISABLE_AUTOUPDATE')
                self.assertEqual(result.returncode, 0, result.stderr)
                environment = self.environment(self.agent_create())
                for setting in RESTRICTED:
                    name = setting.split('=')[0]
                    self.assertEqual([e for e in environment if e == name or e.startswith(name + '=')], [setting])
                for name in ('OPENCODE_DISABLE_SHARE', 'OPENCODE_DISABLE_AUTOUPDATE'):
                    self.assertIn(f'skipping {name}', result.stderr)

    def test_offline_forwards_no_provider_variable(self):
        result = self.run_offline(OPENCODE_CONTAINER_PROVIDER='anthropic')
        self.assertEqual(result.returncode, 0, result.stderr)
        create = self.agent_create()
        self.assertFalse(any(e in ALL_PROVIDER_NAMES for e in self.environment(create)))
        self.assertFalse(any(value in ' '.join(create) for value in self.keys.values()))

    def test_provider_key_per_profile(self):
        for profile, key in KEYS.items():
            with self.subTest(profile=profile):
                other = next(name for name in KEYS.values() if name != key)
                result = self.run_provider(profile=profile, OPENCODE_CONTAINER_ENV_VARS=other, OPENAI_BASE_URL='x')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'network profile={profile}', result.stderr)
                create = self.agent_create()
                self.assertEqual([e for e in self.environment(create) if e in ALL_PROVIDER_NAMES], [key])
                self.assertIn(f'skipping {other}', result.stderr)
                self.assertFalse(any(value in ' '.join(create) for value in self.keys.values()))

    def test_provider_selection_must_match_the_network_profile(self):
        for provider in ('anthropic', 'none'):
            with self.subTest(provider=provider):
                result = self.run_provider(OPENCODE_CONTAINER_PROVIDER=provider)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([e for e in self.environment(self.agent_create()) if e in ALL_PROVIDER_NAMES],
                                 ['ANTHROPIC_API_KEY'])
        result = self.run_provider(profile='openrouter-api', OPENCODE_CONTAINER_PROVIDER='openai')
        self.assert_refused_before_engine(result, 'OPENCODE_CONTAINER_PROVIDER=openai',
                                          'OPENCODE_CONTAINER_NETWORK_PROFILE=openrouter-api')

    def test_restricted_shell_and_probe_get_no_bypass(self):
        for run in (self.run_offline, self.run_provider):
            with self.subTest(mode=run.__name__):
                result = run('--container-shell', '-c', 'echo ok', OPENCODE_CONTAINER_YOLO='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.tail(self.agent_create()), ['/bin/bash', '-c', 'echo ok'])
                self.assertNotIn(BYPASS, self.agent_create())
                result = run('run', 'x', OPENCODE_CONTAINER_YOLO='1')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(BYPASS, self.agent_create())
        control = self.wrapper.parent / 'network/control.py'
        control.write_text(control.read_text() + "if args[0]=='qualification-input': print('f'*32+' 0')\n")
        result = self.run_offline('--container-qualify-probe', OPENCODE_CONTAINER_YOLO='1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.tail(self.agent_create()), ['/usr/bin/python3', '-I',
                                                          '/opt/sandbox-egress/qualification_probe.py', 'probe'])
        self.assertNotIn(BYPASS, self.agent_create())

    # The unrestricted cases of the parent class run once, there.
    test_help_documents_the_agent_variables_and_the_provider_hosts = None
    test_fixed_xdg_bases_and_unrestricted_layout = None
    test_provider_variable_sets_in_unrestricted_mode = None
    test_native_variables_by_name = None
    test_integrations_require_exact_opt_in = None
    test_missing_integration_stops_before_engine = None
    test_yolo_sets_the_permission_outside_shell_mode = None
    test_unrestricted_credentials_only_by_name = None


if __name__ == '__main__':
    unittest.main()
