from kraken.core.system.project import Project
from kraken.core.system.property import Property
from kraken.core.system.task import Task, TaskRelationship


def test__Task__get_relationships_lineage_through_properties(kraken_project: Project) -> None:
    class MyTask(Task):
        prop: Property[str]

        def execute(self) -> None:
            raise NotImplementedError

    t1 = kraken_project.do("t1", MyTask)
    t1.prop.set("Hello, World")

    t2 = kraken_project.do("t2", MyTask)
    t2.prop.set(t1.prop)

    assert list(t2.get_relationships()) == [TaskRelationship(t1, True, False)]
