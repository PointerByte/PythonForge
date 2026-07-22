# `.typing/` — type-checking shim

The package source lives flat under `src/` but is imported and published as
`pythonforge` (see `[tool.setuptools.package-dir]` in `pyproject.toml` and
`setup.py`). At runtime that mapping is handled by the install; at build time
by setuptools.

mypy, however, resolves modules purely from the filesystem: pointed at `src/`
it would name the packages `config`, `transport`, ... and every intra-package
relative import (`from ...errors import`) would appear to escape the top-level
package. Editable installs don't help either — setuptools implements them with
a runtime meta-path finder that mypy cannot follow statically.

`.typing/pythonforge` is a symlink to `../src`, which gives mypy a directory
literally named `pythonforge`, so module names come out as
`pythonforge.config`, `pythonforge.transport.http`, and so on. Hence:

```bash
python -m mypy .typing/pythonforge tests
```

**Windows note:** this is a real symlink (git mode `120000`). Cloning on
Windows needs `git config core.symlinks true` and either Developer Mode or an
elevated shell; otherwise it checks out as a plain text file and mypy will
fail to find the package.
