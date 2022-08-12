from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from kraken.core import Project, Property, Supplier, Task, TaskStatus
from kraken.util.path import try_relative_to

from .check_file_contents_task import as_bytes

if TYPE_CHECKING:
    from kraken.lib.check_file_contents_task import CheckFileContentsTask

DEFAULT_ENCODING = "utf-8"


class RenderFileTask(Task):
    """The RenderFileTask renders a single file to disk.

    The contents of the file can be provided by the :attr:`content` property or by creating a subclass
    that implements the :meth:`get_file_contents` method.

    It is common for a RenderFileTask to be added to the default `apply` task group. A matching check task,
    should you create it, would be a good candidate to add to the default `check` group.
    """

    description = 'Create or update "%(file)s".'

    file: Property[Path]
    content: Property[Union[str, bytes]]
    encoding: Property[str] = Property.default(DEFAULT_ENCODING)

    def create_check(
        self,
        name: str = "{name}.check",
        task_class: type[CheckFileContentsTask] | None = None,
        description: str | None = None,
        group: str | None = "check",
    ) -> CheckFileContentsTask:
        from kraken.lib.check_file_contents_task import CheckFileContentsTask

        task = self.project.do(
            name.replace("{name}", self.name),
            task_class or CheckFileContentsTask,
            description=description,
            group=group,
            file=self.file.value,
            content=self.content.value,
            encoding=self.encoding.value,
        )
        task.add_relationship(self, strict=False)
        return task

    # Task

    def finalize(self) -> None:
        self.file.setmap(lambda path: self.project.directory / path)
        super().finalize()

    def prepare(self) -> TaskStatus | None:
        from kraken.lib.check_file_contents_task import as_bytes

        file = self.file.get()
        if file.is_file() and file.read_bytes() == as_bytes(self.content.get(), self.encoding.get()):
            return TaskStatus.up_to_date()
        return TaskStatus.pending()

    def execute(self) -> TaskStatus:
        file = self.file.get()
        file.parent.mkdir(exist_ok=True)
        content = as_bytes(self.content.get(), self.encoding.get())
        file.write_bytes(content)
        return TaskStatus.succeeded(f"write {len(content)} bytes to {try_relative_to(file)}")


def render_file(
    name: str,
    description: str | None = None,
    group: str | None = "apply",
    create_check: bool = True,
    check_name: str | None = "{name}.check",
    check_group: str | None = "check",
    check_description: str | None = None,
    project: Project | None = None,
    task_class: type[RenderFileTask] | None = None,
    check_task_class: type[CheckFileContentsTask] | None = None,
    *,
    file: str | Path | Property[Path],
    content: str | Property[str],
    encoding: str | Property[str] = DEFAULT_ENCODING,
) -> tuple[RenderFileTask, CheckFileContentsTask | None]:
    from kraken.lib.check_file_contents_task import CheckFileContentsTask

    project = project or Project.current()
    render_task = project.do(
        name,
        task_class or RenderFileTask,
        description=description,
        group=group,
        file=file,
        content=content,
        encoding=encoding,
    )

    if create_check:
        check_task = render_task.create_check(
            check_name.replace("{name}", name),
            check_task_class,
            description=check_description,
            group=check_group,
        )
    else:
        check_task = None

    return render_task, check_task
