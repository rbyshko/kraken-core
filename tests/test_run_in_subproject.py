from pathlib import Path
from textwrap import dedent

from pytest import mark

from kraken.core.cli.main import main
from tests.utils import chdir_context


@mark.parametrize("kind", ["subproject", "root", "subproject-run-root"])
def test_run_kraken_from_subproject(tempdir: Path, kind: str) -> None:
    """
    This test constructs a project with a subproject, runs Kraken from inside that subproject and
    validates that the tasks being run are only from that subproject.

    We test three scenarios:

    1. Running `apply` from the subproject, which should only run the task in the subproject
    2. Running `apply` from the root project, which should run both tasks
    3. Running `:apply` from the subproject, which should run both tasks
    """

    build_script_code = dedent(
        """
        from kraken.core import Project
        from kraken.core.lib.render_file_task import render_file

        sub = Project.current().subproject("sub")

        render_file(name="task", file="root.txt", content="This is in root")
        render_file(name="task", file="sub.txt", content="This is in sub", project=sub)
        """
    )
    build_script = tempdir / ".kraken.py"
    build_script.write_text(build_script_code)

    (tempdir / "sub").mkdir()

    with chdir_context(tempdir if kind == "root" else tempdir / "sub"):
        if kind == "subproject":
            argv = ["run", "--project-dir", "..", "apply"]
        elif kind == "subproject-run-root":
            argv = ["run", "--project-dir", "..", ":apply"]
        else:
            argv = ["run", "apply"]
        try:
            main(argv=argv)
        except SystemExit as exc:
            assert exc.code == 0

    assert (tempdir / "sub.txt").is_file()

    if kind == "root" or kind == "subproject-run-root":
        assert (tempdir / "root.txt").is_file()
    else:
        assert not (tempdir / "root.txt").is_file()
