"""Profile-local, validated workflow bundles with optimistic concurrency."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
from pathlib import Path, PurePosixPath
from uuid import uuid4

import yaml
from tradingagents.workflows import WorkflowBundle, bundled_files
from .workflow_diagram import project_workflow


class WorkflowConflict(ValueError):
    pass


class WorkflowStore:
    def __init__(self, root: Path, config: dict):
        self.root = root
        self.lock = threading.RLock()
        with self.lock:
            self._safe(self.root)
            self.root.mkdir(parents=True, exist_ok=True)
            self._safe(self.root)
            self._safe(self.root / 'active')
            if not (self.root / 'active').exists():
                self._safe(self.root / 'Default')
                self._safe(self.root / 'Default' / 'current')
                if not (self.root / 'Default' / 'current').exists():
                    files = bundled_files()
                    definition = yaml.safe_load(files['workflow.yaml'])
                    definition['analysts'] = list(config['selected_analysts'])
                    for key in ('max_debate_rounds', 'max_risk_discuss_rounds', 'max_tool_rounds'):
                        definition['limits'][key] = config[key]
                    files['workflow.yaml'] = yaml.safe_dump(definition, sort_keys=False, allow_unicode=True)
                    self._save('Default', files, None, create=True)
                self._atomic(self.root / 'active', 'Default')

    @staticmethod
    def _safe(path):
        # lstat detects Windows junctions and other reparse points as well as symlinks.
        try:
            info = path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(info.st_mode) or (getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError(f'Workflow path is a link or reparse point: {path}')

    @staticmethod
    def _paths(paths):
        seen = set()
        for name in paths:
            if not isinstance(name, str) or len(name) > 240 or not name or name.startswith('/'):
                raise ValueError(f'Invalid workflow file path: {name!r}')
            parts = name.split('/')
            for part in parts:
                stem = part.split('.', 1)[0].upper()
                if (not re.fullmatch(r'[A-Za-z0-9_.-]+', part) or part in ('.', '..')
                        or part.endswith('.') or stem in {'CON', 'PRN', 'AUX', 'NUL',
                        *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}):
                    raise ValueError(f'Invalid workflow file path: {name!r}')
            key = name.casefold()
            if key.split('/', 1)[0] == '.files.json' or key in seen:
                raise ValueError(f'Duplicate or reserved workflow file path: {name!r}')
            seen.add(key)
        if any('/'.join(key.split('/')[:i]) in seen for key in seen for i in range(1, len(key.split('/')))):
            raise ValueError('A workflow file cannot also be a directory.')

    def _directory(self, name, *, create=False):
        self._safe(self.root)
        matches = [p.name for p in self.root.iterdir() if p.name.casefold() == name.casefold()]
        if len(matches) > 1 or (matches and matches[0] != name):
            raise WorkflowConflict('A workflow with that name already exists under a different capitalization.')
        directory = self.root / name
        self._safe(directory)
        if create and matches:
            raise WorkflowConflict('A workflow with that name already exists.')
        return directory

    @staticmethod
    def _name(name):
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,63}', name) or name.rstrip() != name:
            raise ValueError('Workflow name must contain 1–64 letters, numbers, spaces, underscores or hyphens.')
        if name.upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
            raise ValueError('Choose a different workflow name.')
        return name

    @staticmethod
    def _files(files):
        if not isinstance(files, dict) or not files or len(files) > 128:
            raise ValueError('Supply a complete workflow bundle of at most 128 files.')
        WorkflowStore._paths(files)
        if any(not isinstance(content, str) for content in files.values()):
            raise ValueError('Workflow files must contain text.')
        if sum(len(v.encode('utf-8')) for v in files.values()) > 1024 * 1024:
            raise ValueError('Workflow bundle exceeds 1 MiB.')
        bundle = WorkflowBundle.from_files(files)
        return bundle, bundle.files

    @staticmethod
    def _revision(files):
        encoded = json.dumps(files, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _atomic(path, value):
        temp = path.with_name('.' + path.name + '-' + uuid4().hex)
        try:
            with temp.open('x', encoding='utf-8', newline='\n') as out:
                out.write(value)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def _read(self, name):
        name = self._name(name)
        directory = self._directory(name)
        self._safe(directory / 'current')
        try:
            generation = (directory / 'current').read_text(encoding='utf-8')
            if not re.fullmatch(r'[0-9a-f]{32}', generation):
                raise ValueError('Invalid workflow generation.')
            folder = directory / generation
            self._safe(folder)
            self._safe(folder / '.files.json')
            paths = json.loads((folder / '.files.json').read_text(encoding='utf-8'))
            if not isinstance(paths, list) or len(paths) > 128:
                raise ValueError('Invalid workflow file index.')
            self._paths(paths)
            files = {}
            for path in paths:
                target = folder
                for part in PurePosixPath(path).parts:
                    target = target / part
                    self._safe(target)
                files[path] = target.read_text(encoding='utf-8')
        except FileNotFoundError as exc:
            raise ValueError(f'Workflow {name!r} or one of its files is unavailable.') from exc
        bundle, files = self._files(files)
        return bundle, files, self._revision(files)

    def _active(self):
        self._safe(self.root)
        self._safe(self.root / 'active')
        return self._name((self.root / 'active').read_text(encoding='utf-8'))

    def catalog(self):
        with self.lock:
            self._safe(self.root)
            names = []
            for p in self.root.iterdir():
                self._safe(p)
                if p.is_dir():
                    self._safe(p / 'current')
                    if (p / 'current').is_file():
                        self._directory(self._name(p.name))
                        names.append(p.name)
            names.sort(key=str.casefold)
            active = self._active()
            bundle, _, _ = self._read(active)
            definition = bundle.definition
            limits = definition['limits']
            effective = {'selected_analysts': list(definition['analysts']),
                         **{key: limits[key] for key in ('max_debate_rounds', 'max_risk_discuss_rounds',
                                                        'max_tool_rounds', 'max_recur_limit')}}
            return {'workflows': names, 'active': active, 'effective_config': effective}

    def load(self, name):
        with self.lock:
            bundle, files, revision = self._read(name)
            return {'name': name, 'files': files, 'revision': revision, 'active': self._active(),
                    'diagram': project_workflow(bundle)}

    def active_bundle(self):
        with self.lock:
            return self._read(self._active())[0]

    def _cleanup(self, directory, folder, paths, *, remove_directory=False, directory_paths=()):
        # Only remove the files we created or read from the validated index.
        self._safe(self.root)
        self._safe(directory)
        self._safe(folder)
        directories = set()
        for name in paths:
            target = folder
            parts = PurePosixPath(name).parts
            for part in parts[:-1]:
                target = target / part
                self._safe(target)
                directories.add(target)
            target = target / parts[-1]
            self._safe(target)
            target.unlink(missing_ok=True)
        index = folder / '.files.json'
        self._safe(index)
        index.unlink(missing_ok=True)
        for name in directory_paths:
            target = folder
            for part in PurePosixPath(name).parts[:-1]:
                target = target / part
                self._safe(target)
                directories.add(target)
        for target in sorted(directories, key=lambda p: len(p.parts), reverse=True):
            self._safe(target)
            try:
                target.rmdir()
            except FileNotFoundError:
                pass
        try:
            folder.rmdir()
        except FileNotFoundError:
            pass
        if remove_directory:
            directory.rmdir()

    def _save(self, name, files, revision, *, create=False):
        name = self._name(name)
        bundle, files = self._files(files)
        diagram = project_workflow(bundle)
        directory = self._directory(name, create=create)
        self._safe(self.root / 'active')
        active = self._active() if (self.root / 'active').exists() else name
        old_folder = None
        old_paths = []
        if create:
            directory.mkdir()
        else:
            _, old_files, current = self._read(name)
            if not isinstance(revision, str) or revision != current:
                raise WorkflowConflict('This workflow changed since it was loaded. Reload it before saving.')
            self._safe(directory / 'current')
            old_generation = (directory / 'current').read_text(encoding='utf-8')
            if not re.fullmatch(r'[0-9a-f]{32}', old_generation):
                raise ValueError('Invalid workflow generation.')
            old_folder = directory / old_generation
            old_paths = list(old_files)
        generation = uuid4().hex
        folder = directory / generation
        staged = []
        created_folder = False
        try:
            folder.mkdir()
            created_folder = True
            self._safe(folder)
            for path, content in files.items():
                parts = PurePosixPath(path).parts
                target = folder
                for part in parts[:-1]:
                    target = target / part
                    self._safe(target)
                    target.mkdir(exist_ok=True)
                    self._safe(target)
                target = target / parts[-1]
                self._safe(target)
                with target.open('x', encoding='utf-8', newline='') as out:
                    staged.append(path)
                    out.write(content)
                    out.flush()
                    os.fsync(out.fileno())
            self._safe(folder / '.files.json')
            self._atomic(folder / '.files.json', json.dumps(list(files), ensure_ascii=False))
            self._safe(directory / 'current')
            self._atomic(directory / 'current', generation)
        except Exception as exc:
            try:
                if created_folder:
                    self._cleanup(directory, folder, staged, remove_directory=create, directory_paths=files)
                elif create:
                    self._safe(directory)
                    directory.rmdir()
            except (OSError, ValueError) as cleanup_error:
                raise ValueError(f'Save failed: {exc}. Cleanup also failed: {cleanup_error}') from exc
            raise
        result = {'name': name, 'files': files, 'revision': self._revision(files), 'active': active,
                  'diagram': diagram}
        if old_folder is not None:
            try:
                self._cleanup(directory, old_folder, old_paths)
            except (OSError, ValueError) as exc:
                result['warning'] = f'Workflow saved, but the previous generation could not be removed: {exc}'
        return result

    def apply(self, data):
        with self.lock:
            action, name = data.get('action'), data.get('name')
            if action == 'preview':
                bundle, _ = self._files(data.get('files'))
                return {'diagram': project_workflow(bundle)}
            if action in ('save', 'save_as'):
                return self._save(name, data.get('files'), data.get('revision'), create=action == 'save_as')
            if action == 'activate':
                bundle, files, revision = self._read(name)
                if data.get('revision') != revision:
                    raise WorkflowConflict('This workflow changed since it was loaded. Reload it before selecting it.')
                diagram = project_workflow(bundle)
                self._safe(self.root / 'active')
                self._atomic(self.root / 'active', name)
                return {'name': name, 'files': files, 'revision': revision, 'active': name,
                        'diagram': diagram}
            raise ValueError('Choose preview, save, save_as, or activate.')
