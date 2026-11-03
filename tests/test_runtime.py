"""Opt-in real rootless Podman checks using disposable state and no credentials."""
import base64
import errno
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import subprocess
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'opencode-wrapper'
USER_NAME = subprocess.check_output(['id', '-un'], text=True).strip()
IMAGE = f'localhost/opencode-sandbox:1.18.3-{USER_NAME}-{os.getuid()}-{os.getgid()}'
ENABLED = os.environ.get('OPENCODE_RUNTIME_TESTS') == '1'


def terminal_shell(command, script, env, cwd, timeout=90):
    """Wait for interactive Bash, then feed one command through a PTY."""
    master, slave = pty.openpty()
    settings = termios.tcgetattr(slave)
    settings[3] &= ~termios.ECHO
    termios.tcsetattr(slave, termios.TCSANOW, settings)
    process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave,
                               cwd=cwd, env=env, start_new_session=True)
    os.close(slave)
    output = bytearray()
    sent = False
    encoded = base64.b64encode(script.encode()).decode()
    payload = f'exec /bin/bash -euc "$(printf %s {encoded} | base64 -d)"\n'.encode()
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                output.extend(chunk)
            if not sent and (b'$ ' in output or b'# ' in output):
                os.write(master, payload)
                sent = True
            if process.poll() is not None and not select.select([master], [], [], 0)[0]:
                break
        else:
            raise AssertionError('Runtime terminal timed out:\n' + output.decode(errors='replace'))
        status = process.wait(timeout=5)
        return subprocess.CompletedProcess(command, status, output.decode(errors='replace'), '')
    finally:
        if process.poll() is None:
            # Terminate this test's process group, including the attached client.
            import signal
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        os.close(master)


@unittest.skipUnless(ENABLED, 'set OPENCODE_RUNTIME_TESTS=1 for real rootless checks')
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        root = ROOT / '.test-state'
        root.mkdir(exist_ok=True)
        self.base = Path(tempfile.mkdtemp(prefix='opencode-runtime-', dir=root)).resolve()
        self.addCleanup(shutil.rmtree, self.base)
        state_root = os.environ.get('OPENCODE_TEST_STATE_ROOT')
        self.home = Path(tempfile.mkdtemp(prefix='opencode-home-', dir=state_root)).resolve()
        self.addCleanup(shutil.rmtree, self.home)
        self.assertEqual(self.home.stat().st_mode & 0o777, 0o700, 'Use tests/run-runtime.sh for native Linux state')
        self.project = self.base / 'project with spaces,commas'
        self.project.mkdir()
        self.env = {'PATH': os.environ['PATH'], 'HOME': str(self.home), 'LANG': 'C.UTF-8',
                    'OPENCODE_CONTAINER_PODMAN': '0'}
        if os.environ.get('CONTAINER_HOST'): self.env['CONTAINER_HOST'] = os.environ['CONTAINER_HOST']
        self.socket = os.environ.get('OPENCODE_CONTAINER_PODMAN_SOCKET', '')
        if not self.socket:
            self.socket = self.env.get('CONTAINER_HOST', 'unix:///run/user/%s/podman/podman.sock' % os.getuid()).removeprefix('unix://')

    def shell(self, script, *options, **env):
        return subprocess.run([str(WRAPPER), '--container-shell', *options],
                              input='set -euo pipefail\n'+script+'\n', capture_output=True, text=True,
                              cwd=self.project, env=self.env|env, timeout=90)

    def pipe_shell(self, script, timeout=60):
        return self.shell(script)

    @classmethod
    def setUpClass(cls):
        # Explicit opt-in failures remain failures, not skipped verification.
        info = subprocess.run(['podman', 'info', '--format',
                               '{{.Host.Security.Rootless}} {{.Host.OS}}'],
                              capture_output=True, text=True, timeout=20)
        if info.returncode or info.stdout.strip() != 'true linux':
            raise AssertionError('Real Linux rootless Podman is required:\n' + info.stdout + info.stderr)
        image = subprocess.run(['podman', 'image', 'exists', IMAGE], timeout=20)
        if image.returncode:
            raise AssertionError('Build the runtime image before opting into tests: ' + IMAGE)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def engine(self, *args, **kwargs):
        if args and args[0] in ('create','run'):
            args=(args[0],'--label','io.opencode.acceptance='+self.base.name,*args[1:])
        return subprocess.run(['podman', *args], capture_output=True, text=True,
                              timeout=kwargs.pop('timeout', 30), **kwargs)

    def start_shell(self, script):
        process = subprocess.Popen(['bash', str(WRAPPER), '--container-shell'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=self.env,
                                   cwd=self.project, start_new_session=True)
        def stop():
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
            process.communicate(timeout=5)
        self.addCleanup(stop)
        process.stdin.write(script)
        process.stdin.close()
        process.stdin = None
        return process

    def wait_file(self, path, process):
        deadline = time.monotonic() + 30
        while not path.exists():
            if process.poll() is not None:
                out, err = process.communicate()
                self.fail('Runtime wrapper exited before readiness:\n' + out + err)
            self.assertLess(time.monotonic(), deadline, 'runtime readiness timed out')
            time.sleep(0.05)

    def session_names(self):
        listing = self.engine('ps', '--all', '--format', '{{.Names}}')
        self.assertEqual(listing.returncode, 0, listing.stderr)
        return [name for name in listing.stdout.splitlines()
                if name.startswith(self.project.name + '-')]

    def unique_project(self):
        self.project = self.base / ('project-' + self.base.name)
        self.project.mkdir()

    def test_nonterminal_input_exit_status_and_pty(self):
        self.unique_project()
        result = self.pipe_shell('test ! -t 0\nprintf "pipe payload\\n"\nexit 125\n')
        self.assertEqual(result.returncode, 125, result.stdout + result.stderr)
        self.assertIn('pipe payload\n', result.stdout)
        self.assertEqual(self.session_names(), [])
        source = self.base / 'commands.sh'
        source.write_text('test ! -t 0\nprintf "file payload\\n"\n')
        with source.open() as stream:
            result = subprocess.run(['bash', str(WRAPPER), '--container-shell'],
                                    stdin=stream, capture_output=True, text=True,
                                    env=self.env, cwd=self.project, timeout=60)
        self.assert_success(result)
        self.assertIn('file payload\n', result.stdout)
        self.assert_success(terminal_shell([str(WRAPPER),'--container-shell'], 'test -t 0\ntest -t 1', self.env, self.project))

    def test_concurrent_reservation_with_stopped_container(self):
        self.unique_project()
        stopped = self.engine('create', '--name', self.project.name + '-08',
                              '--entrypoint', '/bin/true', IMAGE)
        self.assertEqual(stopped.returncode, 0, stopped.stderr)
        stopped_id = stopped.stdout.strip()
        self.addCleanup(self.engine, 'rm', '--force', '--ignore', stopped_id)
        processes = []
        for index in range(2):
            process = self.start_shell(f'touch ready-{index}\nwhile test ! -e release; do sleep 0.05; done\n')
            processes.append(process)
        for index, process in enumerate(processes):
            self.wait_file(self.project / f'ready-{index}', process)
        self.assertEqual(set(self.session_names()),
                         {self.project.name + suffix for suffix in ('-08', '-9', '-10')})
        (self.project / 'release').touch()
        for process in processes:
            out, err = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, out + err)
        self.assertEqual(self.session_names(), [self.project.name + '-08'])

    def test_signal_delivery_owned_cleanup_and_stubborn_process(self):
        self.unique_project()
        unrelated = self.engine('create', '--name', self.project.name + '-08',
                                '--entrypoint', '/bin/true', IMAGE)
        self.assertEqual(unrelated.returncode, 0, unrelated.stderr)
        self.addCleanup(self.engine, 'rm', '--force', '--ignore', unrelated.stdout.strip())
        for sig, status in ((signal.SIGTERM, 143), (signal.SIGINT, 130), (signal.SIGHUP, 129)):
            with self.subTest(signal=sig):
                (self.project / 'ready').unlink(missing_ok=True)
                signame = signal.Signals(sig).name[3:]
                process = self.start_shell(f"trap 'printf {signame} > received; exit 0' {signame}\n"
                                           'touch ready\nwhile :; do sleep 0.1; done\n')
                self.wait_file(self.project / 'ready', process)
                process.send_signal(sig)
                out, err = process.communicate(timeout=25)
                self.assertEqual(process.returncode, status, out + err)
                self.assertEqual((self.project / 'received').read_text(), signame)
                self.assertEqual(self.session_names(), [self.project.name + '-08'])
        (self.project / 'ready').unlink()
        process = self.start_shell("trap '' TERM\ntouch ready\nwhile :; do sleep 0.1; done\n")
        self.wait_file(self.project / 'ready', process)
        start = time.monotonic()
        process.send_signal(signal.SIGTERM)
        out, err = process.communicate(timeout=25)
        self.assertEqual(process.returncode, 143, out + err)
        self.assertLess(time.monotonic() - start, 24)
        self.assertEqual(self.session_names(), [self.project.name + '-08'])

    def test_real_worktrees(self):
        main = self.base / 'main'
        subprocess.run(['git', 'init', '-q', str(main)], check=True)
        subprocess.run(['git', '-C', str(main), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty', '-qm', 'initial'], check=True)
        self.project = self.base / 'linked'
        subprocess.run(['git', '-C', str(main), 'worktree', 'add', '-qb', 'linked', str(self.project)], check=True)
        self.assert_success(self.shell('git status --porcelain\ngit rev-parse --git-common-dir\nprintf worktree > worktree-file',
                                       '--container-git-worktree'))
        self.assertEqual((self.project / 'worktree-file').read_text(), 'worktree')
        self.assertEqual((self.project / 'worktree-file').stat().st_uid, os.getuid())
        self.assertNotEqual(self.shell('git status --porcelain').returncode, 0)

    def test_child_container_host_bind(self):
        script = '''test -S /run/podman/podman.sock
        test "$CONTAINER_HOST" = unix:///run/podman/podman.sock
        podman run --rm --read-only --userns=keep-id --user "$(id -u):$(id -g)" \\
            --volume "$PWD:$PWD:rw" --workdir "$PWD" --entrypoint /bin/sh \\
            ''' + shlex.quote(IMAGE) + ''' -ec 'printf child > child-file'
        test "$(cat child-file)" = child
        '''
        self.assert_success(self.shell(script, OPENCODE_CONTAINER_PODMAN='1',
                                       OPENCODE_CONTAINER_PODMAN_SOCKET=self.socket))
        self.assertEqual((self.project / 'child-file').read_text(), 'child')
        self.assertEqual((self.project / 'child-file').stat().st_uid, os.getuid())

    def test_mounts_state_identity_and_entrypoint(self):
        for name in ('.claude','.agents'):
            path=self.home/name; path.mkdir(); (path/'sentinel').write_text('readonly')
        self.assert_success(self.shell('''
for path in "$HOME/.claude" "$HOME/.agents"; do
    test "$(cat "$path/sentinel")" = readonly
    if touch "$path/write-probe" 2>/dev/null; then exit 20; fi
done
# By-name forwarding delivers only an explicitly allowed synthetic credential.
test "$OPENAI_API_KEY" = synthetic-acceptance
test -z "${UNLISTED_SECRET+x}"
''',OPENAI_API_KEY='synthetic-acceptance',UNLISTED_SECRET='not-forwarded'))
        shutil.copyfile(ROOT/'tests/image-smoke.sh',self.project/'image-smoke.sh')
        result=self.shell('bash -x ./image-smoke.sh')
        self.assert_success(result)
        for relative in ('.config','.local/share','.cache','.local/state'):
            self.assertEqual((self.home/relative/'opencode/sentinel').read_text(),'persistent')
        self.assert_success(self.shell('''
for path in /tmp/opencode-ephemeral /run/opencode-ephemeral /var/tmp/opencode-ephemeral; do test ! -e "$path"; done
for name in XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME; do
    eval 'base=$'"$name"
    test "$(cat "$base/opencode/sentinel")" = persistent
done
'''))
        stub=self.project/'stub'; stub.mkdir()
        (stub/'opencode').write_text('#!/bin/sh\nprintf "%s|%s" "$HOME" "$XDG_CONFIG_HOME"\n')
        (stub/'opencode').chmod(0o755)
        self.assert_success(self.shell('''
actual=$(PATH="$PWD/stub:$PATH" /usr/local/bin/opencode-entrypoint --version)
test "$actual" = "$HOME|$XDG_CONFIG_HOME"
'''))

    def test_build_context(self):
        context=self.base/'context';context.mkdir()
        shutil.copyfile(ROOT/'.dockerignore',context/'.dockerignore')
        shutil.copyfile(ROOT/'opencode-entrypoint',context/'opencode-entrypoint')
        for name in ('unknown','.env','.git/config','auth.json','.local/state/token',
                     'nested/Dockerfile','nested/opencode-entrypoint','nested/.dockerignore'):
            path=context/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('SYNTHETIC')
        recipe=context/'Dockerfile'
        recipe.write_text('FROM '+IMAGE+'\nUSER root\nCOPY opencode-entrypoint /required\nCOPY . /context\n'
                          'RUN test -f /required && test "$(find /context -type f | wc -l)" = 3\n')
        iid=self.base/'context-iid'
        try:
            self.assert_success(self.engine('build','--no-cache','--iidfile',str(iid),str(context),timeout=180))
        finally:
            if iid.exists():self.engine('rmi','--force',iid.read_text().strip())
        recipe.write_text('FROM '+IMAGE+'\nCOPY unknown /must-not-exist\n')
        self.assertNotEqual(self.engine('build',str(context),timeout=90).returncode,0)

    def test_image_default_host_is_removed(self):
        version='acceptance-'+self.base.name
        tag=f'localhost/opencode-sandbox:{version}-{USER_NAME}-{os.getuid()}-{os.getgid()}'
        context=self.base/'env-context';context.mkdir()
        (context/'Dockerfile').write_text('FROM '+IMAGE+'\nENV CONTAINER_HOST=unix:///image-default.sock\n')
        try:
            self.assert_success(self.engine('build','--tag',tag,str(context),timeout=90))
            self.assert_success(self.shell('test -z "${CONTAINER_HOST+x}"',OPENCODE_VERSION=version))
        finally:
            self.engine('rmi','--force',tag)

    def test_containerized_caller_with_remapped_socket(self):
        query=self.engine('info','--format','{{.Host.RemoteSocket.Path}}')
        self.assert_success(query)
        host_socket=query.stdout.strip()
        visible='/run/opencode-test/socket.sock'
        # The caller needs host tooling; select the same runner image explicitly.
        runner=os.environ.get('OPENCODE_TEST_TOOLS_IMAGE','localhost/claude-code:latest')
        command=['podman','run','--rm','--label','io.opencode.acceptance='+self.base.name,'--interactive','--read-only','--userns=keep-id',
                 '--user',f'{os.getuid()}:{os.getgid()}', '--volume',f'{ROOT}:{ROOT}:ro',
                 '--volume',f'{self.base}:{self.base}:rw','--volume',f'{self.home}:{self.home}:rw',
                 '--volume',f'{host_socket}:{visible}:rw','--env','CONTAINER_HOST=unix://'+visible,
                 '--env','HOME='+str(self.home),'--env','OPENCODE_CONTAINER_PODMAN=1',
                 '--workdir',str(self.project),'--entrypoint','/bin/bash',runner,str(WRAPPER),'--container-shell']
        result=subprocess.run(command,input='set -e\ntest -S /run/podman/podman.sock\npodman info >/dev/null\nprintf nested > nested-file\n',
                              capture_output=True,text=True,timeout=90)
        self.assert_success(result)
        self.assertEqual((self.project/'nested-file').read_text(),'nested')

    def test_version(self):
        result=subprocess.run([str(WRAPPER),'--version'],env=self.env,cwd=self.project,
                              capture_output=True,text=True,timeout=60)
        self.assert_success(result)
        self.assertEqual(result.stdout.strip(),'1.18.3')

    def test_opentui_renderer(self):
        env=self.env|{'TERM':'xterm-256color','OPENCODE_DISABLE_AUTOUPDATE':'1',
                      'OPENCODE_DISABLE_DEFAULT_PLUGINS':'1','OPENCODE_DISABLE_MODELS_FETCH':'1'}
        master,slave=pty.openpty()
        import fcntl, struct
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',30,110,0,0))
        process=subprocess.Popen([str(WRAPPER)],cwd=self.project,env=env,
                                 stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
        os.close(slave)
        output=bytearray(); deadline=time.monotonic()+20
        try:
            while time.monotonic()<deadline and process.poll() is None:
                if select.select([master],[],[],0.1)[0]:
                    try: chunk=os.read(master,65536)
                    except OSError as exc:
                        if exc.errno==errno.EIO:break
                        raise
                    output.extend(chunk)
                    if b'\x1b[6n' in chunk: os.write(master,b'\x1b[1;1R')
                    if b'\x1b[c' in chunk: os.write(master,b'\x1b[?1;2c')
            # Quit through the terminal, then let wrapper cleanup finish.
            if process.poll() is None:
                os.write(master,b'\x03');time.sleep(0.5);os.write(master,b'\x03')
            process.wait(timeout=24)
            self.assertIn(process.returncode,(0,130))
            transcript=output.decode(errors='replace')
            (ROOT/'.test-state/renderer-last.txt').write_text(transcript)
            self.assertIn('\x1b[',transcript,transcript)
            self.assertNotIn('Permission denied',transcript)
            self.assertNotIn('Failed to load',transcript)
            # OpenTUI draws its welcome prompt after initializing its renderer.
            self.assertIn('Ask anything',transcript,transcript[-12000:])
            self.assertIn('commands',transcript)
            print('OpenTUI welcome prompt observed; terminal quit status:',process.returncode)
            self.assertEqual(self.session_names(),[])
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM);process.wait(timeout=24)
            os.close(master)

if __name__ == '__main__':
    unittest.main()
