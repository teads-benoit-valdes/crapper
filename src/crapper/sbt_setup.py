"""Files an sbt build needs for a scoverage run, present only while it runs.

The plugin file is added when the build has no sbt-scoverage. The relax file
turns fatal compiler warnings into plain warnings, because scoverage rewrites
the code and a build that treats warnings as errors then fails on code the
user never wrote. Both files are untracked and removed afterwards, so the
user's tree comes out as it went in.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

PLUGIN_FILE = "project/zz-crapper-scoverage.sbt"
RELAX_FILE = "zz-crapper-coverage.sbt"

_PLUGIN = 'addSbtPlugin("org.scoverage" % "sbt-scoverage" % "2.4.4")\n'

# onLoad runs again after every reload, so settings are appended only while a
# project still has a fatal warning to relax.
_RELAX = """\
Global / onLoad ~= { previous =>
  previous.andThen { state =>
    val extracted = Project.extract(state)
    val relax = (options: Seq[String]) =>
      options
        .filterNot(option => option == "-Xfatal-warnings" || option == "-Werror")
        .map(option => if (option.startsWith("-Wconf:")) option.replaceAll(":e(?=,|$)", ":w") else option)
    val settings = extracted.structure.allProjectRefs.flatMap { ref =>
      Seq(Compile, Test).flatMap { configuration =>
        val key = ref / configuration / scalacOptions
        Some(extracted.runTask(key, state)._2).filter(options => relax(options) != options).map(_ => key ~= relax).toSeq
      }
    }
    if (settings.isEmpty) state else extracted.appendWithSession(settings, state)
  }
}
"""


def _has_scoverage(module: Path) -> bool:
    ours = module / PLUGIN_FILE
    candidates = [module / "build.sbt", *module.glob("project/*.sbt")]
    return any(
        "sbt-scoverage" in path.read_text(encoding="utf-8", errors="replace")
        for path in candidates
        if path.is_file() and path != ours
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@contextmanager
def scoverage_files(module: Path) -> Iterator[None]:
    """Hold the files in place for one sbt run and take them away after it."""

    project_existed = (module / "project").is_dir()
    try:
        if not _has_scoverage(module):
            _write(module / PLUGIN_FILE, _PLUGIN)
        _write(module / RELAX_FILE, _RELAX)
        yield
    finally:
        for path in (module / PLUGIN_FILE, module / RELAX_FILE):
            path.unlink(missing_ok=True)
        if not project_existed:
            _remove_if_empty(module / "project")


def _remove_if_empty(directory: Path) -> None:
    try:
        directory.rmdir()
    except OSError:
        pass
