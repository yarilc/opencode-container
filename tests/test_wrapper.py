"""Behavior checks for the wrapper without an engine or provider credentials."""
import json
import itertools
import os
from pathlib import Path
import socket
import signal
import time
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'opencode-container.sh'
FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, sys, time, signal
args = sys.argv[1:]
log = pathlib.Path(os.environ['FAKE_LOG'])
with log.open('a') as f:
    f.write(json.dumps(args) + '\n')
mask = os.umask(0)
os.umask(mask)
with pathlib.Path(str(log) + '.context').open('a') as f:
    f.write(json.dumps({'args': args, 'umask': mask, 'host': os.environ.get('CONTAINER_HOST')}) + '\n')
def publish_cid():
    if '--cidfile' in args and not os.environ.get('FAKE_MISSING_CID'):
        pathlib.Path(args[args.index('--cidfile') + 1]).write_text(os.environ.get('FAKE_CID', 'a' * 64) + '\n')

if args[:2] == ['--remote', '--url']:
    default = os.environ.get('FAKE_SOCKET_ROOTLESS', 'true') + '\n' + args[2][len('unix://'):]
    print(os.environ.get('FAKE_SOCKET_INFO', default))
    sys.exit(int(os.environ.get('FAKE_SOCKET_STATUS', '0')))
elif args[0] == 'info':
    print(os.environ.get('FAKE_INFO', 'true linux false'))
    sys.exit(int(os.environ.get('FAKE_INFO_STATUS', '0')))
elif args[:2] == ['image', 'exists']:
    sys.exit(int(os.environ.get('FAKE_IMAGE_STATUS', '0')))
elif args[0] == 'build':
    sys.exit(int(os.environ.get('FAKE_BUILD_STATUS', '0')))
elif args[0] == 'ps':
    if '--filter' in args:
        print(os.environ.get('FAKE_RECOVER_IDS', ''))
    else:
        print(os.environ.get('FAKE_NAMES', ''))
    sys.exit(int(os.environ.get('FAKE_PS_STATUS', '0')))
elif args[0] == 'inspect' and any('HostConfig.Memory' in a for a in args):
    print(os.environ.get('FAKE_AGENT_BUDGETS', '4294967296 2000000000 512'))
    sys.exit(int(os.environ.get('FAKE_INSPECT_STATUS', '0')))
elif args[0] == 'inspect':
    calls = [json.loads(x) for x in log.read_text().splitlines()]
    creates = [c for c in calls if c[0] == 'create']
    token = next((c[i+1].split('=',1)[1] for c in creates for i,a in enumerate(c[:-1])
                  if a=='--label' and c[i+1].startswith('io.opencode-container.session=')), '')
    print(os.environ.get('FAKE_OWNER',token))
elif args[0] == 'create':
    mode = os.environ.get('FAKE_CREATE_MODE', '')
    if mode:
        pathlib.Path(str(log) + '.pid').write_text(str(os.getpid()))
        if mode in ('before', 'stall-owned'):
            publish_cid()
        if mode == 'cid-on-term':
            def cancel(sig, frame):
                publish_cid()
                sys.exit(125)
            signal.signal(signal.SIGTERM, cancel)
        elif os.environ.get('FAKE_CLIENT_IGNORE_TERM'):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        pathlib.Path(str(log) + '.creating').touch()
        release = pathlib.Path(str(log) + '.release')
        while not release.exists():
            time.sleep(0.01)
        if mode not in ('before', 'stall-owned'):
            publish_cid()
        sys.exit(0)
    if os.environ.get('FAKE_CREATE_WAIT'):
        pathlib.Path(str(log) + '.creating').touch()
        release = pathlib.Path(str(log) + '.release')
        deadline = time.monotonic() + 8
        while not release.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        sys.exit(125)
    if os.environ.get('FAKE_ALL_COLLISIONS'):
        sys.exit(125)
    collision = pathlib.Path(str(log) + '.collision')
    if os.environ.get('FAKE_COLLISION') and not collision.exists():
        collision.touch()
        sys.exit(125)
    if os.environ.get('FAKE_CREATE_FAILURE'):
        print('create failed', file=sys.stderr)
        sys.exit(125)
    publish_cid()
    if os.environ.get('FAKE_CREATE_WARNING'): print('create warning', file=sys.stderr)
    print(os.environ.get('FAKE_STDOUT_CID', 'a' * 64))
elif args[:2] == ['container', 'exists']:
    default = '0' if os.environ.get('FAKE_COLLISION') or os.environ.get('FAKE_ALL_COLLISIONS') else '1'
    sys.exit(int(os.environ.get('FAKE_EXISTS_STATUS', default)))
elif args[0] in ('kill', 'rm'):
    if os.environ.get('FAKE_CONTROL_STALL') in (args[0], 'both'):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(60)
    status = int(os.environ.get('FAKE_' + args[0].upper() + '_STATUS', '0'))
    if status:
        sys.exit(status)
    pid = pathlib.Path(str(log) + '.pid')
    if pid.exists() and (args[0] == 'rm' or not os.environ.get('FAKE_IGNORE_SIGNAL')):
        sig = signal.SIGKILL if args[0] == 'rm' else getattr(signal, 'SIG' + args[args.index('--signal')+1])
        try:
            os.kill(int(pid.read_text()), sig)
        except ProcessLookupError:
            pass
elif args[0] == 'start':
    if os.environ.get('FAKE_WAIT'):
        def stop(sig, frame):
            sys.exit(128 + sig)
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, stop)
        if os.environ.get('FAKE_CLIENT_IGNORE_TERM'):
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        pathlib.Path(str(log) + '.pid').write_text(str(os.getpid()))
        pathlib.Path(str(log) + '.started').touch()
        while True:
            time.sleep(0.05)
    if not os.environ.get('FAKE_NO_STDIN'):
        print('stdin:' + sys.stdin.read())
    sys.exit(int(os.environ.get('FAKE_EXIT', '0')))
'''


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='opencode-container-')
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
        self.state = self.base / 'state'
        self.diagnostics = self.base / 'diagnostics'
        self.diagnostics.mkdir()
        self.env = {'PATH': os.environ['PATH'], 'LANG': 'C.UTF-8'}
        self.env.update(PATH=str(self.bin) + ':' + self.env['PATH'],
                        FAKE_LOG=str(self.log), TMPDIR=str(self.diagnostics),
                        HOME=str(self.base / "home"))
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket_path = self.base / 'podman.sock'
        self.socket.bind(str(self.socket_path))
        self.addCleanup(self.socket.close)
        self.env['OPENCODE_CONTAINER_PODMAN_SOCKET'] = str(self.socket_path)

    def run_wrapper(self, *args, cwd=None, mask=None, **env):
        return subprocess.run([str(WRAPPER), *args], cwd=cwd or self.project,
                              env=self.env | env, input='input payload',
                              text=True, capture_output=True, timeout=10,
                              **({'umask': mask} if mask is not None else {}))

    def calls(self):
        return [json.loads(s) for s in self.log.read_text().splitlines()] if self.log.exists() else []

    def create(self):
        return next(c for c in self.calls() if c[0] == 'create')

    def test_baseline_fixture(self):
        # Record an ordinary launch with the complete verified-engine response.
        result = self.run_wrapper(FAKE_INFO='true linux false')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('stdin:input payload', result.stdout)
        self.assertEqual(self.create()[-1], 'localhost/opencode-cli:latest')

    def test_help_and_arguments(self):
        # Invoke bash explicitly because the wrapper's env shebang needs PATH.
        result = subprocess.run(['/bin/bash', str(WRAPPER), '--container-help'],
                                env=self.env | {'PATH': '/bin', 'CONTAINER_HOST': 'bad'},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls())
        self.assertFalse((self.base / 'home').exists())
        self.assertNotIn('deprecated;', result.stderr)
        for needle in ('Container options:', 'Environment:', 'OPENCODE_CONTAINER_IMAGE',
                       'OPENCODE_CONTAINER_PODMAN ',
                       'OPENCODE_CONTAINER_PODMAN_SOCKET', 'OPENCODE_CONTAINER_YOLO',
                       '1/true/yes enable; empty/0/false/no disable',
                       'including configured ask/deny rules', 'localhost/opencode-cli:latest',
                       'OPENCODE_CONTAINER_STATE_DIR', 'OPENCODE_CONTAINER_MEMORY_LIMIT', '(default: 4g)',
                       'OPENCODE_CONTAINER_CPU_LIMIT', '(default: 2)', 'OPENCODE_CONTAINER_PIDS_LIMIT',
                       '(default: 512)', 'OPENCODE_CONTAINER_RUN_TIMEOUT', '(default: 0',
                       'OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE', 'drops',
                       'do not limit workspace or state storage growth', '/mnt/<letter>',
                       'OPENCODE_CONTAINER_PROVIDER', 'OPENCODE_CONTAINER_ENV_VARS',
                       'OPENCODE_CONTAINER_AGENTS_DIR', 'OPENCODE_CONTAINER_SYSTEM_CONFIG',
                       'anthropic, openai, google, openrouter', 'amazon-bedrock',
                       'azure, opencode or none', '~/.claude is never mounted'):
            self.assertIn(needle, result.stdout)
        result = self.run_wrapper('run', 'hello world', '', '--help', FAKE_INFO='true linux false')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.create()[-4:], ['run', 'hello world', '', '--help'])

    def test_modes(self):
        result = self.run_wrapper('--container-shell', '--container-build',
                                  '--container-git-worktree', 'ignored', FAKE_INFO='true linux false')
        self.assertEqual(result.returncode, 0, result.stderr)
        create = self.create()
        self.assertEqual(create[create.index('--entrypoint')+1], '/bin/bash')
        self.assertNotIn('ignored', create)
        self.assertTrue(any(c[0]=='build' for c in self.calls()))
        self.assertIn(str(self.project.parent), ' '.join(create))
        self.assertEqual(create[create.index('--workdir')+1], str(self.project))

    def assert_no_images(self):
        self.assertFalse(any(c[0] in ('image','build','create') for c in self.calls()))

    def test_launch_validation(self):
        invalid = ['', 'true', 'true linux', 'true linux maybe', 'false linux false',
                   'true darwin false', 'true linux false extra', 'true linux false\n',
                   'true linux false\nextra', 'true linux false\r', 'true linux true']
        for mode, response in itertools.product(((), ('--container-build',), ('--container-shell',)), invalid):
            with self.subTest(mode=mode, response=response):
                self.log.unlink(missing_ok=True)
                result = self.run_wrapper(*mode, FAKE_INFO=response)
                self.assertNotEqual(result.returncode, 0)
                self.assert_no_images()
        for endpoint in ('unix:///', 'unix:////', 'unix://relative', 'tcp://localhost', 'ssh://host'):
            self.log.unlink(missing_ok=True)
            self.assertNotEqual(self.run_wrapper(CONTAINER_HOST=endpoint).returncode, 0)
            self.assertFalse(self.calls())
        self.assertNotEqual(self.run_wrapper(CONTAINER_CONNECTION='named').returncode, 0)
        self.log.unlink(missing_ok=True)
        self.assertNotEqual(self.run_wrapper(FAKE_INFO_STATUS='19').returncode, 0)
        self.assert_no_images()
        for response in ('true linux false', 'true linux true'):
            self.assertEqual(self.run_wrapper(CONTAINER_HOST='unix:///launch.sock', FAKE_INFO=response).returncode, 0)

    def test_exact_delegation_and_remapping(self):
        for mode, value in itertools.product(((), ('--container-build',), ('--container-shell',)),
                                             ('', '0', '1', 'true', 'yes', '01', 'bad', ' 1', '1 ')):
            self.log.unlink(missing_ok=True)
            result = self.run_wrapper(*mode, OPENCODE_CONTAINER_PODMAN=value,
                                      FAKE_SOCKET_INFO='true\n/host path,comma/socket')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(any(c[0]=='--remote' for c in self.calls()), value=='1')
            create = self.create()
            self.assertEqual('--unsetenv' in create, value!='1')
            self.assertEqual('/host path,comma/socket:/run/podman/podman.sock:rw' in create, value=='1')
            for forbidden in ('--privileged', '--security-opt=label=disable'):
                self.assertNotIn(forbidden, create)
            for required in ('--cap-drop=all','--security-opt=no-new-privileges','--pids-limit=512','--userns=keep-id'):
                self.assertIn(required, create)

    def test_socket_validation_and_precedence(self):
        for response in ('', 'true', 'false\n/socket', 'true\nrelative', 'true\n/',
                         'true\n/socket\n', 'true\n/socket\nextra', 'true\n/socket\r'):
            self.log.unlink(missing_ok=True)
            result = self.run_wrapper('--container-build', OPENCODE_CONTAINER_PODMAN='1', FAKE_SOCKET_INFO=response)
            self.assertNotEqual(result.returncode, 0, response)
            self.assert_no_images()
        for path in ('relative.sock', str(self.base/'missing.sock')):
            self.log.unlink(missing_ok=True)
            self.assertNotEqual(self.run_wrapper(OPENCODE_CONTAINER_PODMAN='1', OPENCODE_CONTAINER_PODMAN_SOCKET=path).returncode, 0)
            self.assert_no_images()
        self.log.unlink(missing_ok=True)
        self.assertNotEqual(self.run_wrapper(OPENCODE_CONTAINER_PODMAN='1', FAKE_SOCKET_STATUS='21').returncode, 0)
        self.assert_no_images()
        alias = self.base/'alias.sock'
        alias.symlink_to(self.socket_path)
        self.log.unlink(missing_ok=True)
        result = self.run_wrapper(OPENCODE_CONTAINER_PODMAN='1', OPENCODE_CONTAINER_PODMAN_SOCKET=str(alias), CONTAINER_HOST='unix:///launch-only.sock')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(next(c for c in self.calls() if c[0]=='--remote')[2], 'unix://'+str(self.socket_path))
        context = [json.loads(x) for x in Path(str(self.log)+'.context').read_text().splitlines()]
        self.assertTrue(all(x['host'] in (None, 'unix:///launch-only.sock', 'unix:///launch.sock') for x in context))
        self.log.unlink(missing_ok=True)
        result = self.run_wrapper(OPENCODE_CONTAINER_PODMAN='1', OPENCODE_CONTAINER_PODMAN_SOCKET='', CONTAINER_HOST='unix://'+str(self.socket_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = self.base/'runtime'; (runtime/'podman').mkdir(parents=True)
        (runtime/'podman/podman.sock').symlink_to(self.socket_path)
        self.assertEqual(self.run_wrapper(OPENCODE_CONTAINER_PODMAN='1', OPENCODE_CONTAINER_PODMAN_SOCKET='', XDG_RUNTIME_DIR=str(runtime)).returncode, 0)
        self.socket_path.chmod(0)
        try:
            self.log.unlink(missing_ok=True)
            self.assertNotEqual(self.run_wrapper(OPENCODE_CONTAINER_PODMAN='1').returncode, 0)
            self.assert_no_images()
        finally:
            self.socket_path.chmod(0o600)

    def state_paths(self):
        return [self.base/'home'/p/'opencode' for p in ('.config','.local/share','.cache','.local/state')]

    def test_private_xdg_and_umask(self):
        result = self.run_wrapper(mask=0o022)
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in self.state_paths():
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)
        context = [json.loads(x) for x in Path(str(self.log)+'.context').read_text().splitlines()]
        self.assertTrue(all(x['umask']==(0o077 if x['args'][0]=='create' else 0o022) for x in context))
        for path, mode in itertools.product(self.state_paths(), (0o755, 0o770, 0o600)):
            with self.subTest(path=path, mode=mode):
                path.chmod(mode)
                try:
                    self.log.unlink()
                    result = self.run_wrapper('--container-build')
                    self.assertNotEqual(result.returncode, 0)
                    self.assert_no_images()
                    self.assertEqual(path.stat().st_mode & 0o777, mode)
                finally:
                    path.chmod(0o700)
        for variable in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_STATE_HOME'):
            self.log.unlink(missing_ok=True)
            self.assertNotEqual(self.run_wrapper(**{variable:'relative'}).returncode, 0)
            self.assert_no_images()
        stat = self.bin/'stat'
        stat.write_text('#!/bin/bash\nif [[ "$2" == %u ]]; then echo 99999; else exec /usr/bin/stat "$@"; fi\n')
        stat.chmod(0o755)
        self.log.unlink()
        self.assertNotEqual(self.run_wrapper().returncode, 0)
        self.assert_no_images()

    def test_state_files_broken_links_and_resolution(self):
        for kind in ('file','link'):
            path=self.base/('xdg-'+kind); path.mkdir()
            if kind=='file': (path/'opencode').touch()
            else: (path/'opencode').symlink_to(path/'missing')
            self.log.unlink(missing_ok=True)
            self.assertNotEqual(self.run_wrapper(XDG_CONFIG_HOME=str(path)).returncode, 0)
            self.assert_no_images()
        target=self.base/'physical'; target.mkdir(mode=0o700)
        alias=self.base/'xdg-alias'; alias.symlink_to(target)
        self.log.unlink(missing_ok=True)
        result=self.run_wrapper(XDG_CONFIG_HOME=str(alias))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(f'{target}/opencode:/opencode-home/.config/opencode:rw',self.create())
        appbase=self.base/'appbase'; appbase.mkdir()
        renamed=self.base/'elsewhere'/'renamed'; renamed.mkdir(parents=True,mode=0o700)
        (appbase/'opencode').symlink_to(renamed)
        self.log.unlink()
        result=self.run_wrapper(XDG_CONFIG_HOME=str(appbase))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(f'{renamed}:/opencode-home/.config/opencode:rw',self.create())
        self.log.unlink()
        # Shared state below the workspace binds at its own fixed destination.
        result=self.run_wrapper(XDG_CONFIG_HOME=str(self.project))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(f'{self.project}/opencode:/opencode-home/.config/opencode:rw',self.create())
        (self.project/'opencode').rmdir()

    def test_mount_paths_and_boundaries(self):
        project=self.base/'parent, spaces'/'workspace, spaces'; project.mkdir(parents=True)
        home=self.base/'home, spaces'; home.mkdir()
        (home/'.claude').mkdir(); (home/'.agents').mkdir()
        result=self.run_wrapper(cwd=project,HOME=str(home),OPENCODE_CONTAINER_AGENTS_DIR='1')
        self.assertEqual(result.returncode,0,result.stderr)
        create=self.create()
        self.assertIn(f'{project}:{project}:rw',create)
        for relative in ('.config/opencode','.cache/opencode'):
            self.assertIn(f'{home/relative}:/opencode-home/{relative}:rw',create)
        self.assertIn(f'{home/".agents"}:/opencode-home/.agents:ro',create)
        self.assertFalse(any('.claude' in arg for arg in create))
        self.assertNotIn(f'{home}:{home}:rw',create)
        self.log.unlink()
        alias=self.base/'work-alias'; alias.symlink_to(project)
        result=self.run_wrapper('--container-git-worktree',cwd=alias,HOME=str(home))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.create()[self.create().index('--workdir')+1],str(project))
        self.assertIn(f'{project.parent}:{project.parent}:rw',self.create())
        invalid=self.base/'colon:path'; invalid.mkdir()
        self.log.unlink()
        self.assertNotEqual(self.run_wrapper(cwd=invalid).returncode,0)
        self.assert_no_images()

    def test_tmpfs_and_named_environment(self):
        result=self.run_wrapper(OPENAI_API_KEY='synthetic-secret',OPENCODE_SERVER_PASSWORD='synthetic-pass',UNLISTED_SECRET='unlisted',
                                ANTHROPIC_API_KEY='other-secret',OPENCODE_CONTAINER_PROVIDER='openai')
        self.assertEqual(result.returncode,0,result.stderr)
        create=self.create()
        self.assertIn('--read-only-tmpfs=false',create)
        self.assertEqual([create[i+1] for i,v in enumerate(create) if v=='--tmpfs'],
                         ['/tmp:rw,exec,nosuid,nodev,mode=1777,size=512m',
                          '/run:rw,nosuid,nodev,noexec,mode=1777,size=32m',
                          '/var/tmp:rw,nosuid,nodev,noexec,mode=1777,size=512m',
                          '/opencode-home:rw,exec,nosuid,nodev,mode=1777,size=512m'])
        self.assertIn('OPENAI_API_KEY',create); self.assertIn('OPENCODE_SERVER_PASSWORD',create)
        self.assertNotIn('UNLISTED_SECRET',create); self.assertNotIn('ANTHROPIC_API_KEY',create)
        self.assertNotIn('synthetic-secret',self.log.read_text())
        self.assertNotIn('synthetic-pass',self.log.read_text())

    def forwarded(self):
        create=self.create()
        # Terminal and locale names belong to the unchanged base allowlist.
        return [create[i+1] for i,v in enumerate(create) if v=='--env' and '=' not in create[i+1]
                and create[i+1] not in ('TERM','LANG')]

    def assert_refused(self,result,needle):
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertIn(needle,result.stderr)
        self.assertFalse(self.calls())
        self.assertFalse((self.base/'home').exists())

    def test_claude_state_is_never_mounted(self):
        home=self.base/'home'; claude=home/'.claude'; claude.mkdir(parents=True)
        (claude/'.credentials.json').write_text('{"synthetic": true}')
        (home/'.agents').mkdir()
        for env in ({},{'OPENCODE_CONTAINER_AGENTS_DIR':'1','OPENCODE_CONTAINER_SYSTEM_CONFIG':'yes'}):
            if self.log.exists(): self.log.unlink()
            result=self.run_wrapper(**env)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(any('.claude' in arg for arg in self.create()))

    def test_integrations_require_exact_opt_in(self):
        home=self.base/'home'; agents=home/'.agents'; agents.mkdir(parents=True)
        for value in (None,'','true','yes','01'):
            if self.log.exists(): self.log.unlink()
            env={} if value is None else {'OPENCODE_CONTAINER_AGENTS_DIR':value}
            result=self.run_wrapper(**env)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(any('.agents' in arg for arg in self.create()),value)
            self.assertFalse(any(arg.startswith('/etc/opencode') for arg in self.create()))
        self.log.unlink()
        result=self.run_wrapper(OPENCODE_CONTAINER_AGENTS_DIR='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(f'{agents}:/opencode-home/.agents:ro',self.create())

    def test_missing_opted_in_integration_fails_early(self):
        result=self.run_wrapper(OPENCODE_CONTAINER_AGENTS_DIR='1')
        self.assert_refused(result,'OPENCODE_CONTAINER_AGENTS_DIR')
        self.assertIn(str(self.base/'home'/'.agents'),result.stderr)
        if not Path('/etc/opencode').exists():
            result=self.run_wrapper(OPENCODE_CONTAINER_SYSTEM_CONFIG='1')
            self.assert_refused(result,'OPENCODE_CONTAINER_SYSTEM_CONFIG')

    PROFILES={
        'anthropic':['ANTHROPIC_API_KEY'],
        'openai':['OPENAI_API_KEY','OPENAI_BASE_URL'],
        'google':['GOOGLE_API_KEY','GOOGLE_GENERATIVE_AI_API_KEY','GEMINI_API_KEY'],
        'openrouter':['OPENROUTER_API_KEY'],
        'amazon-bedrock':['AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','AWS_REGION','AWS_BEARER_TOKEN_BEDROCK'],
        'azure':['AZURE_RESOURCE_NAME','AZURE_API_KEY'],
        'opencode':['OPENCODE_API_KEY'],
        'none':[],
    }
    LEGACY=['AZURE_OPENAI_API_KEY','AZURE_OPENAI_ENDPOINT','GH_TOKEN','GITHUB_TOKEN']

    def test_provider_profiles(self):
        every=sorted({n for names in self.PROFILES.values() for n in names}|set(self.LEGACY))
        secrets={name:f'synthetic-{name.lower()}' for name in every}
        for provider,names in self.PROFILES.items():
            with self.subTest(provider=provider):
                if self.log.exists(): self.log.unlink()
                result=self.run_wrapper(OPENCODE_CONTAINER_PROVIDER=provider,**secrets)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(self.forwarded(),names)
                self.assertNotIn('not forwarding',result.stderr)
                log=self.log.read_text()
                for value in secrets.values():
                    self.assertNotIn(value,log)
        if self.log.exists(): self.log.unlink()
        result=self.run_wrapper(OPENCODE_CONTAINER_PROVIDER='amazon-bedrock',AWS_REGION='eu-west-1',AWS_SESSION_TOKEN='')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.forwarded(),['AWS_REGION'])

    def test_unsupported_provider_fails_early(self):
        for value in ('','Anthropic','vertex','openai anthropic','google-vertex'):
            with self.subTest(value=value):
                result=self.run_wrapper(OPENCODE_CONTAINER_PROVIDER=value)
                self.assert_refused(result,'OPENCODE_CONTAINER_PROVIDER')
                self.assertIn('amazon-bedrock',result.stderr)

    def test_unselected_provider_forwards_nothing_and_notifies(self):
        result=self.run_wrapper(OPENAI_API_KEY='synthetic-openai',GITHUB_TOKEN='synthetic-github')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.forwarded(),[])
        notices=[line for line in result.stderr.splitlines() if 'not forwarding' in line]
        self.assertEqual(len(notices),1)
        for needle in ('OPENAI_API_KEY','GITHUB_TOKEN','OPENCODE_CONTAINER_PROVIDER','OPENCODE_CONTAINER_ENV_VARS'):
            self.assertIn(needle,notices[0])
        self.assertNotIn('synthetic-',result.stderr)
        self.assertIn('stdin:input payload',result.stdout)
        for provider in ('none','openai'):
            result=self.run_wrapper(OPENCODE_CONTAINER_PROVIDER=provider,OPENAI_API_KEY='x',GITHUB_TOKEN='y')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('not forwarding',result.stderr)
        result=self.run_wrapper(OPENCODE_CONTAINER_ENV_VARS='GITHUB_TOKEN',OPENAI_API_KEY='x',GITHUB_TOKEN='y')
        notice=next(line for line in result.stderr.splitlines() if 'not forwarding' in line)
        self.assertIn('OPENAI_API_KEY',notice); self.assertNotIn('GITHUB_TOKEN',notice)
        result=self.run_wrapper(UNRELATED='x')
        self.assertNotIn('not forwarding',result.stderr)

    def test_extra_environment_names(self):
        result=self.run_wrapper(OPENCODE_CONTAINER_ENV_VARS='  GH_TOKEN\tDATABASE_URL LANG GH_TOKEN EMPTY_ONE ',
                                OPENCODE_CONTAINER_PROVIDER='none',GH_TOKEN='synthetic-gh',
                                DATABASE_URL='synthetic-db',EMPTY_ONE='')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.forwarded(),['GH_TOKEN','DATABASE_URL'])
        self.assertNotIn('synthetic-',self.log.read_text())
        for token in ('BAD-NAME','X=1','1ABC'):
            with self.subTest(token=token):
                if self.log.exists(): self.log.unlink()
                home=self.base/f'fresh-home-{len(token)}'
                result=self.run_wrapper(OPENCODE_CONTAINER_ENV_VARS=f'GH_TOKEN {token}',HOME=str(home))
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertIn(token,result.stderr)
                self.assertFalse(self.calls()); self.assertFalse(home.exists())
        result=self.run_wrapper(OPENCODE_CONTAINER_ENV_VARS='CONTAINER_HOST HOME XDG_DATA_HOME',
                                OPENCODE_CONTAINER_PODMAN='0')
        self.assertEqual(result.returncode,0,result.stderr)
        for name in ('CONTAINER_HOST','HOME','XDG_DATA_HOME'):
            self.assertIn(f'skipping {name}',result.stderr)
        create=self.create()
        self.assertIn('--unsetenv',create)
        self.assertEqual(create[create.index('--unsetenv')+1],'CONTAINER_HOST')
        self.assertNotIn('CONTAINER_HOST',self.forwarded())
        self.assertEqual([a for a in self.forwarded() if a.startswith(('HOME','XDG'))],[])

    def test_home_layout(self):
        home=self.base/'nonstandard home'
        result=self.run_wrapper(HOME=str(home))
        self.assertEqual(result.returncode,0,result.stderr)
        create=self.create()
        env=[create[i+1] for i,v in enumerate(create) if v=='--env']
        for assignment in ('HOME=/opencode-home','XDG_CONFIG_HOME=/opencode-home/.config',
                           'XDG_DATA_HOME=/opencode-home/.local/share','XDG_CACHE_HOME=/opencode-home/.cache',
                           'XDG_STATE_HOME=/opencode-home/.local/state'):
            self.assertIn(assignment,env)
        for relative in ('.config','.local/share','.cache','.local/state'):
            self.assertIn(f'{home/relative/"opencode"}:/opencode-home/{relative}/opencode:rw',create)
        volumes=[create[i+1] for i,v in enumerate(create) if v=='--volume']
        self.assertFalse(any(v.split(':')[1].startswith(str(home)) for v in volumes))
        self.assertIn('/opencode-home:rw,exec,nosuid,nodev,mode=1777,size=512m',create)

    def test_deprecated_shim(self):
        shim = ROOT / 'opencode-wrapper'
        link = self.base / 'opencode-link'
        link.symlink_to(shim)
        for entry in (shim, link):
            with self.subTest(entry=entry.name):
                self.log.unlink(missing_ok=True)
                result = subprocess.run([str(entry), 'run', 'hello world', '', '--help'],
                                        cwd=self.project, env=self.env, input='input payload',
                                        text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr.count('opencode-wrapper: deprecated; use opencode-container.sh'), 1)
                self.assertEqual(self.create()[-4:], ['run', 'hello world', '', '--help'])
                self.assertIn('stdin:input payload', result.stdout)
        self.log.unlink()
        result = subprocess.run([str(shim)], cwd=self.project, env=self.env | {'FAKE_EXIT': '125'},
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 125, result.stderr)

    def test_labels_use_common_namespace(self):
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 0, result.stderr)
        create = self.create()
        labels = sorted(create[i+1].split('=', 1)[0] for i, v in enumerate(create) if v == '--label')
        self.assertEqual(labels, ['io.opencode-container.instance', 'io.opencode-container.managed',
                                  'io.opencode-container.session', 'io.opencode-container.workspace',
                                  'io.opencode-container.workspace-name'])
        self.assertFalse(any(arg.startswith('io.opencode.') for arg in create))

    def test_image_and_ignored_version_variables(self):
        for env in ({'OPENCODE_CONTAINER_VERSION':'1.19.0'},{'OPENCODE_VERSION':'1.17.1'},
                    {'OPENCODE_CONTAINER_VERSION':'','OPENCODE_VERSION':'x/y'}):
            with self.subTest(env=env):
                self.log.unlink(missing_ok=True)
                result=self.run_wrapper(FAKE_IMAGE_STATUS='1',**env)
                self.assertEqual(result.returncode,0,result.stderr)
                for name in env:
                    self.assertEqual(result.stderr.count(f'{name} is ignored; the OpenCode version is pinned in Containerfile'),1)
                build=next(c for c in self.calls() if c[0]=='build')
                self.assertNotIn('--build-arg',build)
                self.assertEqual(self.create()[-1],'localhost/opencode-cli:latest')
        self.log.unlink()
        custom='localhost/opencode-custom:test'
        result=self.run_wrapper(FAKE_IMAGE_STATUS='1',OPENCODE_CONTAINER_IMAGE=custom)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(['image','exists',custom],self.calls())
        self.assertEqual(next(c for c in self.calls() if c[0]=='build')[2],custom)
        self.assertEqual(self.create()[-1],custom)
        for value in ('bad image','bad\timage'):
            self.log.unlink(missing_ok=True)
            result=self.run_wrapper(OPENCODE_CONTAINER_IMAGE=value)
            self.assertEqual(result.returncode,1,result.stderr)
            self.assertIn('OPENCODE_CONTAINER_IMAGE',result.stderr)
            self.assertFalse(self.calls())
        recipe=(ROOT/'Containerfile').read_text()
        self.assertIn('ARG OPENCODE_VERSION=1.18.3\n',recipe)
        self.assertNotIn('USER_NAME',recipe)
        self.assertFalse((ROOT/'opencode-entrypoint').exists())

    def test_isolated_state_directory(self):
        state=self.base/'isolated'/'state'
        result=self.run_wrapper(OPENCODE_CONTAINER_STATE_DIR=str(state),mask=0o022)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(state.stat().st_mode & 0o777,0o700)
        for relative in ('.config','.local/share','.cache','.local/state'):
            self.assertEqual((state/relative/'opencode').stat().st_mode & 0o777,0o700)
        create=self.create()
        self.assertIn(f'{state}:/opencode-home:rw',create)
        self.assertFalse(any(a.startswith('/opencode-home:') for a in create))
        self.assertFalse((self.base/'home').exists())
        volumes=[create[i+1] for i,v in enumerate(create) if v=='--volume']
        self.assertEqual(len(volumes),2)
        foreign=self.base/'shared'; foreign.mkdir(mode=0o755)
        cases=('relative/state','',str(foreign),str(self.project),str(self.project/'state'),
               str(self.project.parent),'/bad:colon')
        for value in cases:
            with self.subTest(value=value):
                self.log.unlink(missing_ok=True)
                result=self.run_wrapper(OPENCODE_CONTAINER_STATE_DIR=value)
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertIn('OPENCODE_CONTAINER_STATE_DIR' if value!=str(foreign) else 'must be private',result.stderr)
                self.assertFalse(self.calls())
        self.assertFalse((self.project/'state').exists())
        self.assertEqual(foreign.stat().st_mode & 0o777,0o755)

    def test_budgets(self):
        result=self.run_wrapper()
        self.assertEqual(result.returncode,0,result.stderr)
        create=self.create()
        for flag in ('--memory=4294967296','--cpus=2','--pids-limit=512','--cap-drop=all',
                     '--security-opt=no-new-privileges'):
            self.assertIn(flag,create)
        self.assertNotIn('--timeout',create)
        inspect=[c for c in self.calls() if c[0]=='inspect' and any('HostConfig.Memory' in a for a in c)]
        self.assertEqual(len(inspect),1)
        names=[c[0] for c in self.calls()]
        self.assertLess(names.index('create'),self.calls().index(inspect[0]))
        self.assertLess(self.calls().index(inspect[0]),names.index('start'))
        self.log.unlink()
        result=self.run_wrapper(OPENCODE_CONTAINER_MEMORY_LIMIT='8g',OPENCODE_CONTAINER_CPU_LIMIT='1.5',
                                OPENCODE_CONTAINER_PIDS_LIMIT='1024',
                                FAKE_AGENT_BUDGETS='8589934592 1500000000 1024')
        self.assertEqual(result.returncode,0,result.stderr)
        for flag in ('--memory=8589934592','--cpus=1.5','--pids-limit=1024'):
            self.assertIn(flag,self.create())
        for env in ({'OPENCODE_CONTAINER_YOLO':'1'},{'OPENCODE_CONTAINER_PODMAN':'1'}):
            self.log.unlink()
            self.assertEqual(self.run_wrapper('--container-shell',**env).returncode,0)
            for flag in ('--memory=4294967296','--cpus=2','--pids-limit=512','--cap-drop=all'):
                self.assertIn(flag,self.create())
        invalid={'OPENCODE_CONTAINER_MEMORY_LIMIT':('','  ','0','-1','max','4','4t','1.5g','2000000g'),
                 'OPENCODE_CONTAINER_CPU_LIMIT':('','0','0.0','-1','1.2345','2000','max','a'),
                 'OPENCODE_CONTAINER_PIDS_LIMIT':('','0','-1','max','4194305','1.5')}
        for name,values in invalid.items():
            for value in values:
                with self.subTest(name=name,value=value):
                    self.log.unlink(missing_ok=True)
                    home=self.base/'budget-home'
                    result=self.run_wrapper(HOME=str(home),**{name:value})
                    self.assertEqual(result.returncode,1,result.stderr)
                    self.assertIn(name,result.stderr)
                    self.assertFalse(self.calls()); self.assertFalse(home.exists())

    def test_budget_inspection_failures(self):
        for env in ({'FAKE_AGENT_BUDGETS':'0 0 0'},{'FAKE_AGENT_BUDGETS':'4294967296 2000000000 -1'},
                    {'FAKE_AGENT_BUDGETS':'1 2000000000 512'},{'FAKE_INSPECT_STATUS':'125'}):
            with self.subTest(env=env):
                self.log.unlink(missing_ok=True)
                result=self.run_wrapper(**env)
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertIn('session not started',result.stderr)
                names=[c[0] for c in self.calls()]
                self.assertNotIn('start',names)
                self.assertIn(['rm','--force','--ignore','--time','0','a'*64],self.calls())
        self.assertIn('cgroup v2',self.run_wrapper(FAKE_AGENT_BUDGETS='0 0 0').stderr)

    def test_lifetime(self):
        for value,expected in (('','0'),('0','0'),('60','60'),('7','7')):
            with self.subTest(value=value):
                self.log.unlink(missing_ok=True)
                result=self.run_wrapper(OPENCODE_CONTAINER_RUN_TIMEOUT=value)
                self.assertEqual(result.returncode,0,result.stderr)
                create=self.create()
                if expected=='0': self.assertNotIn('--timeout',create)
                else: self.assertEqual(create[create.index('--timeout')+1],expected)
        for value in ('-1','1.5','abc','0007','12345678901'):
            with self.subTest(value=value):
                self.log.unlink(missing_ok=True)
                result=self.run_wrapper(OPENCODE_CONTAINER_RUN_TIMEOUT=value)
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertIn('OPENCODE_CONTAINER_RUN_TIMEOUT',result.stderr)
                self.assertFalse(self.calls())
        slow=self.bin/'podman'
        original=slow.read_text()
        slow.write_text(original.replace("elif args[0] == 'start':","elif args[0] == 'start' and os.environ.get('FAKE_SLOW'):\n    time.sleep(float(os.environ['FAKE_SLOW'])); sys.exit(255)\nelif args[0] == 'start':",1))
        result=self.run_wrapper(OPENCODE_CONTAINER_RUN_TIMEOUT='2',FAKE_SLOW='2.2')
        self.assertEqual(result.returncode,255,result.stderr)
        self.assertIn('session lifetime limit reached (2 s); exit status 255',result.stderr)
        result=self.run_wrapper(OPENCODE_CONTAINER_RUN_TIMEOUT='30',FAKE_EXIT='3')
        self.assertEqual(result.returncode,3,result.stderr)
        self.assertNotIn('lifetime',result.stderr)

    def test_sensitive_workspaces(self):
        home=self.base/'home'; home.mkdir()
        def refused(cwd, *args, **env):
            self.log.unlink(missing_ok=True)
            state=self.base/'guard-state'
            result=self.run_wrapper(*args,cwd=cwd,HOME=str(home),XDG_CONFIG_HOME=str(state),**env)
            return result,state
        for cwd in (home,Path('/'),Path('/etc'),Path('/tmp'),Path('/usr')):
            with self.subTest(cwd=cwd):
                result,state=refused(cwd)
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertIn('refusing sensitive workspace',result.stderr)
                self.assertFalse(self.calls()); self.assertFalse(state.exists())
        child=home/'project'; child.mkdir()
        result,_=refused(child,'--container-git-worktree')
        self.assertEqual(result.returncode,1,result.stderr)
        link=self.base/'etc-link'; link.symlink_to('/etc')
        result,_=refused(link)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertIn('/etc',result.stderr)
        for value in ('true','yes','01',''):
            result,_=refused(home,OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE=value)
            self.assertEqual(result.returncode,1,result.stderr)
        result,_=refused(home,OPENCODE_CONTAINER_ALLOW_UNSAFE_WORKSPACE='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('WARNING: sensitive workspace explicitly exposed read/write',result.stderr)
        self.log.unlink()
        result=self.run_wrapper(cwd=child,HOME=str(home))
        self.assertEqual(result.returncode,0,result.stderr)

    def test_yolo_switch(self):
        allow = 'OPENCODE_PERMISSION={"*":"allow"}'
        self.run_wrapper()
        baseline = self.create()
        for value in ('1', 'true', 'TRUE', 'Yes'):
            with self.subTest(value=value):
                self.log.unlink()
                result = self.run_wrapper(OPENCODE_CONTAINER_YOLO=value)
                self.assertEqual(result.returncode, 0, result.stderr)
                create = self.create()
                self.assertEqual(create.count(allow), 1)
                env_positions = [i for i, v in enumerate(create) if v == '--env']
                self.assertGreater(create.index(allow), max(i for i in env_positions if '=' not in create[i+1]))
                def surface(args):
                    pairs = [(v, args[i+1]) for i, v in enumerate(args[:-1])
                             if v in ('--volume', '--env', '--unsetenv', '--cap-drop=all', '--userns=keep-id')]
                    return [p for p in pairs if p[1] != allow] + [a for a in args if a.startswith('--security-opt') or a.startswith('--pids')]
                self.assertEqual(surface(create), surface(baseline))
        for value in ('', '0', 'false', 'NO'):
            with self.subTest(value=value):
                self.log.unlink()
                result = self.run_wrapper(OPENCODE_CONTAINER_YOLO=value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(any('OPENCODE_PERMISSION' in a for a in self.create()))
        self.log.unlink()
        result = self.run_wrapper(OPENCODE_CONTAINER_YOLO='maybe')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('OPENCODE_CONTAINER_YOLO', result.stderr)
        self.assertFalse(self.calls())
        result = self.run_wrapper(OPENCODE_CONTAINER_YOLO='1', OPENCODE_PERMISSION='{"edit":"ask"}')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('OPENCODE_PERMISSION', result.stderr)
        self.assertFalse(self.calls())
        result = self.run_wrapper(OPENCODE_PERMISSION='{"edit":"ask"}')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('OPENCODE_PERMISSION', self.create())
        self.assertNotIn(allow, self.create())

    def test_image_inspection_and_build(self):
        for status in ('0','1','125'):
            self.log.unlink(missing_ok=True)
            result=self.run_wrapper(FAKE_IMAGE_STATUS=status)
            self.assertEqual(result.returncode,125 if status=='125' else 0,result.stderr)
            self.assertEqual(any(c[0]=='build' for c in self.calls()),status=='1')
            self.assertEqual(any(c[0]=='create' for c in self.calls()),status!='125')
        self.log.unlink()
        self.assertEqual(self.run_wrapper('--container-build').returncode,0)
        build=next(c for c in self.calls() if c[0]=='build')
        self.assertEqual(build[-1],str(ROOT))
        self.assertEqual(build[build.index('--file')+1],str(ROOT/'Containerfile'))
        self.assertNotIn('--build-arg',build)
        self.assertEqual(build[build.index('--tag')+1],'localhost/opencode-cli:latest')
        self.assertEqual(self.create()[-1],'localhost/opencode-cli:latest')
        self.log.unlink()
        self.assertEqual(self.run_wrapper('--container-build',FAKE_BUILD_STATUS='23').returncode,23)
        self.assertFalse(any(c[0]=='create' for c in self.calls()))

    def start_wrapper(self, *options, **env):
        return subprocess.Popen([str(WRAPPER), *options], cwd=self.project,
                                env=self.env | env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_marker(self, suffix, proc):
        marker = Path(str(self.log) + suffix)
        deadline = time.monotonic() + 5
        while not marker.exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(marker.exists(), 'fake engine did not become ready')

    def assert_owned_removal(self):
        removals = [c for c in self.calls() if c[0] == 'rm']
        self.assertEqual(removals, [['rm', '--force', '--ignore', '--time', '0', 'a' * 64]])

    def finish_process(self, proc):
        # A failed assertion must not leave a blocked fake client behind.
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=5)
        pid = Path(str(self.log) + '.pid')
        if pid.exists():
            try:
                os.kill(int(pid.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_stalled_creation_cancellation_is_bounded(self):
        for mode in ('stall', 'stall-owned', 'cid-on-term'):
            with self.subTest(mode=mode):
                self.log.unlink(missing_ok=True)
                Path(str(self.log) + '.creating').unlink(missing_ok=True)
                Path(str(self.log) + '.release').unlink(missing_ok=True)
                proc = self.start_wrapper(FAKE_CREATE_MODE=mode,
                                          FAKE_CLIENT_IGNORE_TERM='1' if mode == 'stall' else '')
                try:
                    self.wait_marker('.creating', proc)
                    start = time.monotonic()
                    proc.send_signal(signal.SIGTERM)
                    time.sleep(0.1)
                    proc.send_signal(signal.SIGHUP)
                    out, err = proc.communicate(timeout=24)
                    self.assertLess(time.monotonic() - start, 21)
                    self.assertEqual(proc.returncode, 143, out + err)
                    self.assertFalse(any(c[0] == 'start' for c in self.calls()))
                    if mode == 'stall':
                        self.assertIn('creation outcome unresolved', err)
                        self.assertFalse(any(c[0] == 'rm' for c in self.calls()))
                    else:
                        self.assert_owned_removal()
                    self.assertEqual(list(self.diagnostics.iterdir()), [])
                finally:
                    self.finish_process(proc)

    def test_attached_signal_matrix(self):
        for shell, sig in itertools.product((False, True),
                                           (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)):
            with self.subTest(shell=shell, sig=sig):
                self.log.unlink(missing_ok=True)
                Path(str(self.log) + '.started').unlink(missing_ok=True)
                proc = self.start_wrapper(*(('--container-shell',) if shell else ()), FAKE_WAIT='1')
                try:
                    self.wait_marker('.started', proc)
                    proc.send_signal(sig)
                    out, err = proc.communicate(timeout=10)
                    self.assertEqual(proc.returncode, 128 + sig, out + err)
                    self.assertEqual([c for c in self.calls() if c[0] == 'kill'],
                                     [['kill', '--signal', signal.Signals(sig).name[3:], 'a' * 64]])
                    self.assertIn('--sig-proxy=false', next(c for c in self.calls() if c[0] == 'start'))
                    self.assert_owned_removal()
                    self.assert_client_gone()
                finally:
                    self.finish_process(proc)

    def assert_client_gone(self):
        pid = int(Path(str(self.log) + '.pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_stubborn_sessions_and_control_failures_are_bounded(self):
        cases = ({}, {'FAKE_CONTROL_STALL': 'kill'}, {'FAKE_KILL_STATUS': '125'},
                 {'FAKE_CONTROL_STALL': 'rm', 'FAKE_CLIENT_IGNORE_TERM': '1'},
                 {'FAKE_RM_STATUS': '125'},
                 {'FAKE_CONTROL_STALL': 'both', 'FAKE_CLIENT_IGNORE_TERM': '1'})
        for env in cases:
            with self.subTest(env=env):
                self.log.unlink(missing_ok=True)
                Path(str(self.log) + '.started').unlink(missing_ok=True)
                proc = self.start_wrapper(FAKE_WAIT='1', FAKE_IGNORE_SIGNAL='1', **env)
                try:
                    self.wait_marker('.started', proc)
                    start = time.monotonic()
                    proc.send_signal(signal.SIGTERM)
                    time.sleep(0.1)
                    proc.send_signal(signal.SIGHUP)
                    out, err = proc.communicate(timeout=24)
                    elapsed = time.monotonic() - start
                    self.assertLess(elapsed, 21)
                    self.assertEqual(proc.returncode, 143, out + err)
                    if not env:
                        self.assertGreaterEqual(elapsed, 3.8)
                    if env.get('FAKE_CONTROL_STALL') in ('kill', 'both') or env.get('FAKE_KILL_STATUS'):
                        self.assertIn('cannot forward TERM', err)
                    if env.get('FAKE_CONTROL_STALL') in ('rm', 'both') or env.get('FAKE_RM_STATUS'):
                        self.assertIn('cannot remove owned container', err)
                    self.assert_owned_removal()
                    self.assert_client_gone()
                    self.assertEqual(list(self.diagnostics.iterdir()), [])
                finally:
                    self.finish_process(proc)

    def test_application_status_survives_cleanup_failure(self):
        for status, removal in itertools.product(('0', '23', '125'), ('ok', 'failed', 'stalled')):
            with self.subTest(status=status, removal=removal):
                self.log.unlink(missing_ok=True)
                result = self.run_wrapper(FAKE_EXIT=status,
                                          FAKE_RM_STATUS='125' if removal == 'failed' else '0',
                                          FAKE_CONTROL_STALL='rm' if removal == 'stalled' else '')
                self.assertEqual(result.returncode, int(status), result.stderr)
                self.assertEqual(len([c for c in self.calls() if c[0] == 'create']), 1)
                self.assert_owned_removal()
                self.assertEqual('cannot remove owned container' in result.stderr, removal != 'ok')
                self.assertEqual(list(self.diagnostics.iterdir()), [])
    def test_names_failures_and_owned_records(self):
        prefix='my-project'
        result=self.run_wrapper(FAKE_NAMES=prefix+'-08\n'+prefix+'-12\n'+prefix+'-999999999999999999999\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.create()[self.create().index('--name')+1],prefix+'-13')
        for env, count in (({'FAKE_PS_STATUS':'125'},0),({'FAKE_ALL_COLLISIONS':'1'},20),
                           ({'FAKE_CREATE_FAILURE':'1'},1),({'FAKE_CREATE_FAILURE':'1','FAKE_EXISTS_STATUS':'125'},1)):
            self.log.unlink()
            result=self.run_wrapper(**env)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(len([c for c in self.calls() if c[0]=='create']),count)
            self.assertFalse(any(c[0]=='rm' for c in self.calls()))
        self.log.unlink()
        result=self.run_wrapper(FAKE_COLLISION='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len([c for c in self.calls() if c[0]=='create']),2)
        self.log.unlink()
        result=self.run_wrapper(FAKE_CREATE_WARNING='1')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('create warning',result.stderr)
        self.assert_owned_removal()
        for cid in ('bad','a'*64+'\nextra','a'*64+'\n'):
            self.log.unlink()
            result=self.run_wrapper(FAKE_CID=cid)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(any(c[0] in ('start','rm') for c in self.calls()))
        self.log.unlink()
        result=self.run_wrapper(FAKE_MISSING_CID='1',FAKE_RECOVER_IDS='b'*64,FAKE_OWNER='different-session')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(c[0]=='rm' for c in self.calls()))

    def test_creation_signals(self):
        for mode,sig in itertools.product(('before','after'),(signal.SIGTERM,signal.SIGINT,signal.SIGHUP)):
            self.log.unlink(missing_ok=True)
            for suffix in ('.creating','.release'): Path(str(self.log)+suffix).unlink(missing_ok=True)
            proc=self.start_wrapper(FAKE_CREATE_MODE=mode)
            try:
                self.wait_marker('.creating',proc)
                session=next(self.diagnostics.iterdir())
                self.assertEqual(session.stat().st_mode & 0o777,0o700)
                self.assertEqual((session/'error').stat().st_mode & 0o777,0o600)
                if (session/'cid').exists(): self.assertEqual((session/'cid').stat().st_mode & 0o777,0o600)
                proc.send_signal(sig)
                time.sleep(0.05)
                Path(str(self.log)+'.release').touch()
                out,err=proc.communicate(timeout=24)
                self.assertEqual(proc.returncode,128+sig,out+err)
                self.assertFalse(any(c[0]=='start' for c in self.calls()))
                self.assert_owned_removal()
            finally:
                self.finish_process(proc)

    def test_tty_and_mixed_streams(self):
        import pty
        master,slave=pty.openpty()
        try:
            for input_terminal,output_terminal in ((True,True),(True,False),(False,True)):
                self.log.unlink(missing_ok=True)
                proc=subprocess.Popen([str(WRAPPER)],cwd=self.project,env=self.env|{'FAKE_NO_STDIN':'1'},
                                      stdin=slave if input_terminal else subprocess.DEVNULL,
                                      stdout=slave if output_terminal else subprocess.PIPE,stderr=subprocess.PIPE)
                out,err=proc.communicate(timeout=10)
                self.assertEqual(proc.returncode,0,err)
                self.assertIn('--interactive',self.create())
                self.assertEqual('--tty' in self.create(),input_terminal and output_terminal)
        finally:
            os.close(master);os.close(slave)


if __name__ == '__main__':
    unittest.main()
