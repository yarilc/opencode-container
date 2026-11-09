"""Credential-free checks that the runtime image inputs are pinned (B05).

Same parsing as the claude-container reference. OpenCode has no network policy
yet, so there is no tested-CLI cross-check until the Wave 3 network port.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('opencode-ai', '@fission-ai/openspec')
TOOLSET = ('bash', 'bubblewrap', 'bzip2', 'ca-certificates', 'coreutils', 'curl', 'diffutils',
           'file', 'findutils', 'gawk', 'git', 'grep', 'jq', 'less', 'nano', 'patch', 'podman',
           'procps', 'python3', 'ripgrep', 'sed', 'tar', 'unzip', 'util-linux', 'xz-utils', 'zip')
VERSION = re.compile(r'\d+\.\d+\.\d+')


def pins(recipe):
    """Return (base reference, {ARG name: default}, installed package specifiers)."""
    lines = recipe.replace('\\\n', ' ').splitlines()
    bases = [line.split()[1] for line in lines if line.startswith('FROM ')]
    if len(bases) != 1:
        raise ValueError('expected exactly one FROM line')
    args = dict(re.findall(r'^ARG ([A-Z_]+)=(\S+)$', recipe, re.MULTILINE))
    installs = []
    for line in lines:
        if 'npm install' in line or 'npm i ' in line:
            for command in line.split('&&'):
                if 'npm install' not in command and 'npm i ' not in command:
                    continue
                for token in command.split():
                    token = token.strip('"\'')
                    if token.startswith('@') or (not token.startswith('-') and '/' not in token
                                                 and token not in ('npm', 'install', 'i')):
                        for name, value in args.items():
                            token = token.replace('${' + name + '}', value).replace('$' + name, value)
                        installs.append(token)
    return bases[0], args, installs


def violations(recipe):
    found = []
    base, _, installs = pins(recipe)
    if not re.fullmatch(r'[a-z0-9./:-]+@sha256:[a-f0-9]{64}', base):
        found.append('base image is not pinned by digest: ' + base)
    seen = {}
    for spec in installs:
        name, _, version = spec.rpartition('@')
        if not name:
            found.append('unpinned package: ' + spec)
            continue
        if not VERSION.fullmatch(version):
            found.append('package is not pinned to an exact version: ' + spec)
        seen[name] = version
    for package in PACKAGES:
        if package not in seen:
            found.append('required package is not installed with a pinned version: ' + package)
    if 'anomalyco/opencode' in recipe:
        found.append('third-party OpenCode image is referenced')
    apt = re.search(r'apt-get install[^&]*', recipe.replace('\\\n', ' '))
    listed = set(apt[0].split()) if apt else set()
    for tool in TOOLSET:
        if tool not in listed:
            found.append('toolset package is missing: ' + tool)
    return found


class ImagePinTests(unittest.TestCase):
    def setUp(self):
        self.recipe = (ROOT / 'Containerfile').read_text()

    def test_shipped_recipe_is_pinned(self):
        self.assertEqual(violations(self.recipe), [])
        _, args, _ = pins(self.recipe)
        self.assertRegex(args['OPENCODE_VERSION'], VERSION)
        self.assertRegex(args['OPENSPEC_VERSION'], VERSION)

    def test_mutated_recipes_are_rejected(self):
        digest = re.search(r'@sha256:[a-f0-9]{64}', self.recipe)
        cases = {
            'tag-only base': self.recipe.replace(digest[0], '') if digest else self.recipe,
            'latest package': self.recipe.replace('"@fission-ai/openspec@${OPENSPEC_VERSION}"',
                                                  '@fission-ai/openspec@latest'),
            'unversioned package': self.recipe.replace('"opencode-ai@${OPENCODE_VERSION}"', 'opencode-ai'),
            'version range': self.recipe.replace('ARG OPENSPEC_VERSION=1.16.0', 'ARG OPENSPEC_VERSION=^1.16.0'),
            'missing package': self.recipe.replace('"opencode-ai@${OPENCODE_VERSION}" \\\n', ''),
            'third-party image': self.recipe.replace('docker.io/library/node:22-bookworm-slim',
                                                     'ghcr.io/anomalyco/opencode'),
            'missing toolset package': self.recipe.replace('        nano \\\n', ''),
        }
        for name, recipe in cases.items():
            with self.subTest(name=name):
                self.assertNotEqual(recipe, self.recipe)
                self.assertTrue(violations(recipe))


if __name__ == '__main__':
    unittest.main()
