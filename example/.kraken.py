# ::pythonpath .

from my_tasks import DockerBuildTask, WriteDockerfileTask

from kraken.core import Project

project = Project.current()
dockerfile = project.do("writeDockerfile", WriteDockerfileTask, content="FROM ubuntu:latest\nRUN echo Hello World")
project.do("dockerBuild", DockerBuildTask, dockerfile=dockerfile.dockerfile)
