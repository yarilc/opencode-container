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
import sys
import tempfile
import termios
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'network'))
import agent_budgets  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'opencode-container.sh'
USER_NAME = subprocess.check_output(['id', '-un'], text=True).strip()
IMAGE = 'localhost/opencode-cli:latest'
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
                    'OPENCODE_CONTAINER_PODMAN': '0', 'OPENCODE_CONTAINER_NETWORK': 'unrestricted',
                    'OPENCODE_CONTAINER_MAINTENANCE': '1'}
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
            args=(args[0],'--label','io.opencode-container.acceptance='+self.base.name,*args[1:])
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

    def test_pseudo_terminals_and_device_masks(self):
        # Interactive tools open their own PTY: the session must allocate one,
        # while /dev/shm and /run/secrets stay empty read-only masks.
        probe = r'''import os
import pathlib
import pty
master, slave = pty.openpty()
assert os.ttyname(slave).startswith('/dev/pts/'), os.ttyname(slave)
os.close(master); os.close(slave)
for path in ('/dev/shm', '/run/secrets'):
    assert list(pathlib.Path(path).iterdir()) == [], path
    try:
        (pathlib.Path(path) / 'probe').write_text('x')
    except OSError:
        pass
    else:
        raise AssertionError(path + ' is writable')
print('pty-and-masks-ok')
'''
        result = self.shell('python3 -c ' + shlex.quote(probe))
        self.assert_success(result)
        self.assertIn('pty-and-masks-ok', result.stdout)

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
        # ~/.claude is never mounted and ~/.agents only on exact opt-in.
        self.assert_success(self.shell('''
test ! -e "$HOME/.claude"
test ! -e "$HOME/.agents"
'''))
        self.assert_success(self.shell('''
test "$HOME" = /opencode-home
test ! -e "$HOME/.claude"
test "$(cat "$HOME/.agents/sentinel")" = readonly
if touch "$HOME/.agents/write-probe" 2>/dev/null; then exit 20; fi
''',OPENCODE_CONTAINER_AGENTS_DIR='1'))
        # By-name forwarding delivers only the selected provider and listed names.
        self.assert_success(self.shell('''
test "$OPENAI_API_KEY" = synthetic-acceptance
test "$DATABASE_URL" = synthetic-extra
test -z "${ANTHROPIC_API_KEY+x}"
test -z "${GH_TOKEN+x}"
test -z "${UNLISTED_SECRET+x}"
''',OPENCODE_CONTAINER_PROVIDER='openai',OPENCODE_CONTAINER_ENV_VARS='DATABASE_URL',
            OPENAI_API_KEY='synthetic-acceptance',ANTHROPIC_API_KEY='synthetic-other',
            GH_TOKEN='synthetic-github',DATABASE_URL='synthetic-extra',UNLISTED_SECRET='not-forwarded'))
        result=self.shell('test -z "${OPENAI_API_KEY+x}"',OPENAI_API_KEY='synthetic-acceptance')
        self.assert_success(result)
        self.assertNotIn('synthetic-acceptance',result.stderr)
        shutil.copyfile(ROOT/'tests/image-smoke.sh',self.project/'image-smoke.sh')
        result=self.shell(f'EXPECTED_UID={os.getuid()} EXPECTED_GID={os.getgid()} bash -x ./image-smoke.sh')
        self.assert_success(result)
        for relative in ('.config','.local/share','.cache','.local/state'):
            self.assertEqual((self.home/relative/'opencode/sentinel').read_text(),'persistent')
        self.assert_success(self.shell('''
for path in /tmp/opencode-ephemeral /var/tmp/opencode-ephemeral; do test ! -e "$path"; done
for name in XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME; do
    eval 'base=$'"$name"
    test "$(cat "$base/opencode/sentinel")" = persistent
done
'''))
        # The dedicated home is ephemeral apart from the four state directories.
        self.assert_success(self.shell('printf scratch > "$HOME/scratch"'))
        self.assert_success(self.shell('test ! -e "$HOME/scratch"'))

    def test_isolated_state_persists(self):
        state=self.home/'isolated'
        self.assert_success(self.shell('''
test "$HOME" = /opencode-home
for name in XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME; do
    eval 'base=$'"$name"
    test -d "$base/opencode" && test -w "$base/opencode"
done
printf kept > "$HOME/notes"
''',OPENCODE_CONTAINER_STATE_DIR=str(state)))
        self.assertEqual((state/'notes').read_text(),'kept')
        self.assertEqual(state.stat().st_mode & 0o777,0o700)
        self.assertFalse((self.home/'.config/opencode').exists())
        self.assert_success(self.shell('test "$(cat "$HOME/notes")" = kept',OPENCODE_CONTAINER_STATE_DIR=str(state)))

    def cgroup(self, **env):
        # A controller file the engine did not create counts as unlimited.
        result=self.shell('''
grep -E '^(CapInh|CapPrm|CapEff|CapBnd|CapAmb|NoNewPrivs):' /proc/self/status
for file in memory.max pids.max cpu.max; do printf '%s=%s\n' "$file" "$(cat /sys/fs/cgroup/$file 2>/dev/null || echo max)"; done
grep '^Max processes' /proc/self/limits
''',**env)
        self.assert_success(result)
        return result

    def engine_budgets(self):
        """Delegated controllers and process mechanism of the engine, by the launcher's rule."""
        def info(template):
            return subprocess.run(['podman', 'info', '--format', template], env=self.env, check=True,
                                  capture_output=True, text=True, timeout=60).stdout.strip()
        delegated = agent_budgets.delegated(info('{{.Host.CgroupControllers}}'), info('{{.Host.CgroupManager}}'))
        return delegated, agent_budgets.process_mechanism(delegated, info('{{.Host.Kernel}}'))

    def test_effective_hardening_and_budgets(self):
        # Budgets apply as the engine allows: cgroup limits only for delegated
        # controllers, the process rlimit as fallback, and a notice otherwise.
        controllers,mechanism=self.engine_budgets()
        for env,(memory,pids,cpu) in (({},('4294967296','512','200000 100000')),
                                      ({'OPENCODE_CONTAINER_MEMORY_LIMIT':'1g','OPENCODE_CONTAINER_CPU_LIMIT':'1.5',
                                        'OPENCODE_CONTAINER_PIDS_LIMIT':'256'},('1073741824','256','150000 100000'))):
            for delegated in ('0','1'):
                with self.subTest(env=env,delegated=delegated):
                    extra={'OPENCODE_CONTAINER_PODMAN':delegated}
                    if delegated=='1': extra['OPENCODE_CONTAINER_PODMAN_SOCKET']=self.socket
                    result=self.cgroup(**env,**extra)
                    out=result.stdout
                    for field in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'):
                        self.assertRegex(out,field+r':\s*0000000000000000')
                    self.assertRegex(out,r'NoNewPrivs:\s*1')
                    self.assertIn('memory.max='+(memory if 'memory' in controllers else 'max')+'\n',out)
                    self.assertIn('pids.max='+(pids if mechanism=='cgroup' else 'max')+'\n',out)
                    if 'cpu' in controllers:
                        self.assertIn('cpu.max='+cpu,out)
                    else:
                        self.assertRegex(out,r'cpu\.max=max\b')
                    if mechanism=='rlimit':
                        self.assertRegex(out,r'Max processes\s+'+pids+r'\s+'+pids+r'\s')
                    for budget,controller in (('memory','memory'),('CPU','cpu')):
                        notice=f'agent {budget} budget not enforced'
                        if controller in controllers:
                            self.assertNotIn(notice,result.stderr)
                        else:
                            self.assertIn(notice,result.stderr)
                    rlimit=f'agent process budget enforced through the process rlimit ({pids} tasks'
                    self.assertEqual(rlimit in result.stderr,mechanism=='rlimit',result.stderr)
                    self.assertEqual('agent process budget not enforced' in result.stderr,mechanism=='none',result.stderr)

    def test_process_limit_enforced(self):
        # A process budget is enforced, not just reported. Under the rlimit
        # fallback, container startup also counts, so the budget leaves room.
        if self.engine_budgets()[1]=='none':
            self.skipTest('the engine enforces no process budget')
        result=self.shell('python3 - <<\'CHECK\'\nimport subprocess\nchildren = []\ntry:\n'
                          '    for _ in range(200):\n        children.append(subprocess.Popen(["sleep", "30"]))\n'
                          'except (BlockingIOError, OSError):\n    print("PIDS_BUDGET_ENFORCED")\n'
                          'finally:\n    [child.kill() for child in children]\nCHECK\n',
                          OPENCODE_CONTAINER_PIDS_LIMIT='128')
        self.assert_success(result)
        self.assertIn('PIDS_BUDGET_ENFORCED',result.stdout)

    def test_tools_without_capabilities(self):
        result=self.shell('''git init -q repo && git -C repo -c user.name=t -c user.email=t@example.invalid commit -q --allow-empty -m x
openspec --version >/dev/null
bwrap --ro-bind / / --dev /dev --proc /proc --unshare-all true && echo BWRAP_OK
podman run --rm --pull=never --entrypoint true '''+shlex.quote(IMAGE)+''' && echo DELEGATED_CHILD_OK
''',OPENCODE_CONTAINER_PODMAN='1',OPENCODE_CONTAINER_PODMAN_SOCKET=self.socket)
        self.assert_success(result)
        for marker in ('BWRAP_OK','DELEGATED_CHILD_OK'):
            self.assertIn(marker,result.stdout)

    def test_lifetime_limit(self):
        before=time.monotonic()
        result=self.shell('sleep 30',OPENCODE_CONTAINER_RUN_TIMEOUT='3')
        elapsed=time.monotonic()-before
        self.assertNotEqual(result.returncode,0)
        self.assertLess(elapsed,25)
        self.assertIn('session lifetime limit reached (3 s); exit status',result.stderr)
        self.lifetime_status=result.returncode
        print(f'lifetime expiry status: {result.returncode}')
        result=self.shell('exit 4',OPENCODE_CONTAINER_RUN_TIMEOUT='30')
        self.assertEqual(result.returncode,4)
        self.assertNotIn('lifetime',result.stderr)

    def test_sensitive_home_refused(self):
        result=subprocess.run([str(WRAPPER),'--container-shell'],input='exit 0\n',capture_output=True,text=True,
                              cwd=self.home,env=self.env,timeout=60)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertIn('refusing sensitive workspace',result.stderr)

    def test_build_context(self):
        context=self.base/'context';context.mkdir()
        shutil.copyfile(ROOT/'.containerignore',context/'.containerignore')
        for name in ('unknown','.env','.git/config','auth.json','.local/state/token','opencode-entrypoint',
                     'nested/Containerfile','nested/opencode-entrypoint','nested/.containerignore',
                     'network/relay.py','network/mux.py','network/proxy.py','network/bin/sandbox-egress-guard',
                     'nested/network/relay.py'):
            path=context/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('SYNTHETIC')
        recipe=context/'Containerfile'
        recipe.write_text('FROM '+IMAGE+'\nUSER root\nCOPY . /context\n'
                          'RUN test "$(find /context -type f | wc -l)" = 4 && test -f /context/Containerfile '
                          '&& test -f /context/.containerignore && test -f /context/network/relay.py '
                          '&& test -f /context/network/mux.py\n')
        iid=self.base/'context-iid'
        try:
            self.assert_success(self.engine('build','--no-cache','--iidfile',str(iid),str(context),timeout=180))
        finally:
            if iid.exists():self.engine('rmi','--force',iid.read_text().strip())
        recipe.write_text('FROM '+IMAGE+'\nCOPY opencode-entrypoint /must-not-exist\n')
        self.assertNotEqual(self.engine('build',str(context),timeout=90).returncode,0)

    def test_image_default_host_is_removed(self):
        version='acceptance-'+self.base.name
        tag=f'localhost/opencode-sandbox:{version}-{USER_NAME}-{os.getuid()}-{os.getgid()}'
        context=self.base/'env-context';context.mkdir()
        (context/'Containerfile').write_text('FROM '+IMAGE+'\nENV CONTAINER_HOST=unix:///image-default.sock\n')
        try:
            self.assert_success(self.engine('build','--tag',tag,str(context),timeout=90))
            self.assert_success(self.shell('test -z "${CONTAINER_HOST+x}"',OPENCODE_CONTAINER_IMAGE=tag))
        finally:
            self.engine('rmi','--force',tag)

    def test_containerized_caller_with_remapped_socket(self):
        query=self.engine('info','--format','{{.Host.RemoteSocket.Path}}')
        self.assert_success(query)
        host_socket=query.stdout.strip()
        visible='/run/opencode-test/socket.sock'
        # The caller needs host tooling; select the same runner image explicitly.
        runner=os.environ.get('OPENCODE_TEST_TOOLS_IMAGE','localhost/claude-code:latest')
        command=['podman','run','--rm','--label','io.opencode-container.acceptance='+self.base.name,'--interactive','--read-only','--userns=keep-id',
                 '--user',f'{os.getuid()}:{os.getgid()}', '--volume',f'{ROOT}:{ROOT}:ro',
                 '--volume',f'{self.base}:{self.base}:rw','--volume',f'{self.home}:{self.home}:rw',
                 '--volume',f'{host_socket}:{visible}:rw','--env','CONTAINER_HOST=unix://'+visible,
                 '--env','HOME='+str(self.home),'--env','OPENCODE_CONTAINER_PODMAN=1',
                 '--env','OPENCODE_CONTAINER_NETWORK=unrestricted',
                 '--workdir',str(self.project),'--entrypoint','/bin/bash',runner,str(WRAPPER),'--container-shell']
        result=subprocess.run(command,input='set -e\ntest -S /run/podman/podman.sock\npodman info >/dev/null\nprintf nested > nested-file\n',
                              capture_output=True,text=True,timeout=90)
        self.assert_success(result)
        self.assertEqual((self.project/'nested-file').read_text(),'nested')

    def test_version(self):
        result=subprocess.run([str(WRAPPER),'--version'],env=self.env,cwd=self.project,
                              capture_output=True,text=True,timeout=60)
        self.assert_success(result)
        self.assertEqual(result.stdout.strip(),'1.19.5')

    def resolved_permission(self, **env):
        result=subprocess.run([str(WRAPPER),'debug','config'],env=self.env|{'OPENCODE_DISABLE_AUTOUPDATE':'1',
                              'OPENCODE_DISABLE_MODELS_FETCH':'1','OPENCODE_DISABLE_DEFAULT_PLUGINS':'1'}|env,
                              cwd=self.project,capture_output=True,text=True,timeout=120)
        self.assert_success(result)
        import json
        return json.loads(result.stdout[result.stdout.index('{'):]).get('permission')

    def test_yolo_resolved_permission(self):
        # The pinned OpenCode merges OPENCODE_PERMISSION into its resolved configuration.
        self.assertEqual(self.resolved_permission(OPENCODE_CONTAINER_YOLO='1'),{'*':'allow'})
        self.assertNotEqual(self.resolved_permission(),{'*':'allow'})

    def owned_ids(self, all_states=False):
        # Sessions carry only the ownership label; the working directory names the workspace,
        # whose path contains commas that label filters cannot express.
        listing=self.engine('ps',*(['--all'] if all_states else []),'--filter','label=io.opencode-container.session',
                            '--format','{{.ID}}').stdout.split()
        return ' '.join(ident for ident in listing
                        if self.engine('inspect','--format','{{.Config.WorkingDir}}',ident).stdout.strip()
                        ==str(self.project))

    def test_session_carries_only_the_ownership_label(self):
        script='''
for i in $(seq 1 100); do test -e "$PWD/ready" && break; sleep 0.1; done
'''
        process=subprocess.Popen([str(WRAPPER),'--container-shell'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,text=True,env=self.env,cwd=self.project)
        try:
            deadline=time.monotonic()+60; ids=''
            while time.monotonic()<deadline and not ids:
                ids=self.owned_ids()
                time.sleep(0.2)
            self.assertTrue(ids,'session container not found by its ownership label')
            labels=self.engine('inspect','--format','{{json .Config.Labels}}',ids.split()[0]).stdout
            import json
            keys=[k for k in json.loads(labels) if k.startswith('io.opencode')]
            self.assertEqual(keys,['io.opencode-container.session'])
            (self.project/'ready').write_text('')
            out,err=process.communicate('set -e\n'+script+'exit 7\n',timeout=60)
        finally:
            if process.poll() is None: process.kill(); process.wait()
        self.assertEqual(process.returncode,7,err)
        self.assertEqual(self.owned_ids(all_states=True),'')

    def test_read_only_state(self):
        # OPENCODE_CONTAINER_READONLY_STATE mounts the existing state read-only below the ephemeral home.
        self.assert_success(self.shell('printf kept > "$XDG_CONFIG_HOME/opencode/readonly-sentinel"'))
        result=self.shell('''test "$(cat "$XDG_CONFIG_HOME/opencode/readonly-sentinel")" = kept
for name in XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME; do
    eval 'base=$'"$name"
    if touch "$base/opencode/forbidden" 2>/dev/null; then echo "WRITABLE $name"; exit 10; fi
done
printf scratch > "$HOME/scratch"''',OPENCODE_CONTAINER_READONLY_STATE='1')
        self.assert_success(result)
        self.assertFalse((self.home/'.config/opencode/forbidden').exists())

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

    # Toolchain library

    def toolchain(self, *args, **env):
        return subprocess.run([str(WRAPPER), '--container-toolchain', *args], cwd=self.project,
                              env=self.env | env, text=True, capture_output=True, timeout=300)

    def archive_recipe(self, name, commands, **values):
        import hashlib, io, json, tarfile
        native = Path(tempfile.mkdtemp(prefix='opencode-toolchain-', dir=os.environ.get('OPENCODE_TEST_STATE_ROOT')))
        self.addCleanup(shutil.rmtree, native)
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
            for directory in (name + '-1', name + '-1/bin'):
                info = tarfile.TarInfo(directory)
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                archive.addfile(info)
            for command, output in commands.items():
                data = ('#!/bin/sh\necho ' + output + '-"$*"\n').encode()
                info = tarfile.TarInfo(name + '-1/bin/' + command)
                info.size, info.mode = len(data), 0o755
                archive.addfile(info, io.BytesIO(data))
        path = native / (name + '.tar.gz')
        path.write_bytes(buffer.getvalue())
        recipe = {'schema': 1, 'name': name, 'version': '1', 'default': True, 'path': ['bin'],
                  'env': {name.upper() + '_HOME': {'toolchain': ''}}, 'check': [next(iter(commands)), 'check'],
                  'source': {'archive': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'strip_components': 1}}
        recipe.update(values)
        recipe_path = native / (name + '.json')
        recipe_path.write_text(json.dumps(recipe))
        return recipe_path

    def test_toolchain_library_sources_environment_and_read_only_mount(self):
        import json, uuid
        library = self.home / '.local/share/sandbox-toolchains'
        self.assert_success(self.toolchain('add', str(self.archive_recipe('hello', {'hello': 'hello'}))))
        # A default toolchain providing node and python3 never replaces the runtime's own.
        self.assert_success(self.toolchain('add', str(self.archive_recipe(
            'shadow', {'node': 'fake-node', 'python3': 'fake-python'}, env={}))))
        failing = self.archive_recipe('broken', {'broken': 'broken'}, check=['false'], env={})
        result = self.toolchain('add', str(failing))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('toolchain check failed for broken', result.stderr)
        self.assertFalse((library / 'broken').exists())
        context = Path(tempfile.mkdtemp(prefix='opencode-image-', dir=os.environ.get('OPENCODE_TEST_STATE_ROOT')))
        self.addCleanup(shutil.rmtree, context)
        (context / 'opt/imgtool/bin').mkdir(parents=True)
        (context / 'opt/imgtool/bin/imgtool').write_text('#!/bin/sh\necho image-tool\n')
        (context / 'opt/imgtool/bin/imgtool').chmod(0o755)
        (context / 'Containerfile').write_text('FROM scratch\nCOPY opt /opt\n')
        image = 'localhost/opencode-toolchain-test-' + uuid.uuid4().hex
        self.addCleanup(subprocess.run, ['podman', 'image', 'rm', '--force', '--ignore', image + ':latest'],
                        capture_output=True, timeout=60)
        self.assert_success(subprocess.run(['podman', 'build', '--tag', image + ':latest', str(context)],
                                           text=True, capture_output=True, timeout=120))
        digest = subprocess.run(['podman', 'image', 'inspect', '--format', '{{.Digest}}', image + ':latest'],
                                text=True, capture_output=True, timeout=60).stdout.strip()
        recipe = context.parent / (context.name + '-imgtool.json')
        self.addCleanup(recipe.unlink, missing_ok=True)
        recipe.write_text(json.dumps({'schema': 1, 'name': 'imgtool', 'version': '1', 'default': False,
                                      'source': {'image': image + '@' + digest, 'path': '/opt/imgtool'},
                                      'check': ['imgtool']}))
        self.assert_success(self.toolchain('add', str(recipe)))
        listing = self.toolchain('list')
        self.assert_success(listing)
        for name in ('hello', 'shadow', 'imgtool'):
            self.assertIn(name + '\t', listing.stdout)
        result = self.shell('''test "$(hello a)" = hello-a
test "$HELLO_HOME" = /toolchains/hello
test "$(command -v node)" = /usr/local/bin/node
test "$(command -v python3)" = /usr/bin/python3
test "$XDG_DATA_HOME" = /opencode-home/.local/share
test "$(. /toolchains/shadow/env.sh && node b)" = fake-node-b
test "$(. /toolchains/imgtool/env.sh && imgtool)" = image-tool
if command -v imgtool; then exit 9; fi
grep -q 'hello 1' /toolchains/toolchains.md
python3 -c 'import json; assert [t["name"] for t in json.load(open("/toolchains/index.json"))["toolchains"]] == ["hello", "imgtool", "shadow"]'
if touch /toolchains/new 2>/dev/null; then exit 10; fi
if rm /toolchains/hello/bin/hello 2>/dev/null; then exit 11; fi
test -x /toolchains/hello/bin/hello
echo toolchains-ok''')
        self.assert_success(result)
        self.assertIn('toolchains-ok', result.stdout)
        self.assert_success(self.toolchain('remove', 'imgtool'))
        self.assertFalse((library / 'imgtool').exists())

    def test_toolchain_library_can_be_omitted(self):
        result = self.shell('test ! -e /toolchains\necho omitted', OPENCODE_CONTAINER_TOOLCHAINS='0')
        self.assert_success(result)
        self.assertIn('omitted', result.stdout)


if __name__ == '__main__':
    unittest.main()
