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
WRAPPER = ROOT / 'opencode-wrapper'
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
elif args[0] == 'inspect':
    calls = [json.loads(x) for x in log.read_text().splitlines()]
    creates = [c for c in calls if c[0] == 'create']
    token = next((c[i+1].split('=',1)[1] for c in creates for i,a in enumerate(c[:-1])
                  if a=='--label' and c[i+1].startswith('io.opencode.session=')), '')
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
        self.tmp = tempfile.TemporaryDirectory(prefix='opencode-wrapper-')
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
        self.assertEqual(self.create()[-1].split(':')[0], 'localhost/opencode-sandbox')

    def test_help_and_arguments(self):
        # Invoke bash explicitly because the wrapper's env shebang needs PATH.
        result = subprocess.run(['/bin/bash', str(WRAPPER), '--container-help'],
                                env=self.env | {'PATH': '/bin', 'CONTAINER_HOST': 'bad'},
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.calls())
        self.assertFalse((self.base / 'home').exists())
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
            self.log.unlink()
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
        self.assertIn(f'{target}/opencode:{target}/opencode:rw',self.create())
        appbase=self.base/'appbase'; appbase.mkdir()
        renamed=self.base/'elsewhere'/'renamed'; renamed.mkdir(parents=True,mode=0o700)
        (appbase/'opencode').symlink_to(renamed)
        self.log.unlink()
        result=self.run_wrapper(XDG_CONFIG_HOME=str(appbase))
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(f'{renamed}:{renamed.parent}/opencode:rw',self.create())
        self.log.unlink()
        self.assertNotEqual(self.run_wrapper(XDG_CONFIG_HOME=str(self.project)).returncode,0)
        self.assert_no_images()

    def test_mount_paths_and_boundaries(self):
        project=self.base/'parent, spaces'/'workspace, spaces'; project.mkdir(parents=True)
        home=self.base/'home, spaces'; home.mkdir()
        (home/'.claude').mkdir(); (home/'.agents').mkdir()
        result=self.run_wrapper(cwd=project,HOME=str(home))
        self.assertEqual(result.returncode,0,result.stderr)
        create=self.create()
        for path in (project,home/'.config/opencode',home/'.cache/opencode'):
            self.assertIn(f'{path}:{path}:rw',create)
        for path in (home/'.claude',home/'.agents'):
            self.assertIn(f'{path}:{path}:ro',create)
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
        result=self.run_wrapper(OPENAI_API_KEY='synthetic-secret',OPENCODE_SERVER_PASSWORD='synthetic-pass',UNLISTED_SECRET='unlisted')
        self.assertEqual(result.returncode,0,result.stderr)
        create=self.create()
        self.assertIn('--read-only-tmpfs=false',create)
        self.assertEqual([create[i+1] for i,v in enumerate(create) if v=='--tmpfs'],
                         ['/tmp:rw,exec,nosuid,nodev,mode=1777,size=512m',
                          '/run:rw,nosuid,nodev,noexec,mode=1777,size=32m',
                          '/var/tmp:rw,nosuid,nodev,noexec,mode=1777,size=512m'])
        self.assertIn('OPENAI_API_KEY',create); self.assertIn('OPENCODE_SERVER_PASSWORD',create)
        self.assertNotIn('UNLISTED_SECRET',create)
        self.assertNotIn('synthetic-secret',self.log.read_text())
        self.assertNotIn('synthetic-pass',self.log.read_text())

    def test_entrypoint_home(self):
        stub=self.bin/'opencode'
        stub.write_text('#!/bin/sh\nprintf "%s|%s|%s" "$HOME" "$USER" "$1"\n');stub.chmod(0o755)
        for home in (str(self.base/'nonstandard'),None):
            env=self.env.copy()
            if home is None: env.pop('HOME',None)
            else: env['HOME']=home
            result=subprocess.run([str(ROOT/'opencode-entrypoint'),'payload'],env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            expected=home or '/home/'+subprocess.check_output(['id','-un'],text=True).strip()
            self.assertEqual(result.stdout,expected+'|'+subprocess.check_output(['id','-un'],text=True).strip()+'|payload')

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
        self.assertIn('OPENCODE_VERSION=1.18.3',build)
        for field,cmd in (('USER_NAME',['id','-un']),('USER_ID',['id','-u']),('GROUP_ID',['id','-g'])):
            self.assertIn(field+'='+subprocess.check_output(cmd,text=True).strip(),build)
        self.assertTrue(self.create()[-1].startswith('localhost/opencode-sandbox:1.18.3-'))
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
