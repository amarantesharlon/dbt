from dbt.cli.types import Command
from dbt.tests.util import run_dbt
from tests.functional.fixtures.happy_path_fixture import (  # noqa: F401
    happy_path_project,
    happy_path_project_files,
)

for i in Command:
    print(i.value)

commands = [
    "build",
    "clean",
    "compile",
    # "clone",
    # "generate",
    # "serve",
    "debug",
    "deps",
    # "init",
    "list",
    "parse",
    "run",
    # "run-operation",
    "seed",
    # "show", # need to specify a resource
    # "snapshot",
    # "freshness",
    "test",
    "retry",
]
# flake8: noqa
## Idea 1: define a mapping of commands-> actual commands to run, and a list to skip, make sure they add up to all commands
# Run everything to make sure we are not missing any commands
#
# we can run everything?
def test_run_commmands(
    happy_path_project,
):
    for dbt_command in commands:
        run_dbt([dbt_command])


#### Idea 2:
# compose all of the nodes being executed in the command before and test that all node type are covered?
# Need to figure out what all nodes are


from dbt.contracts.graph.nodes import BaseNode


def find_end_classes(cls):
    end_classes = []
    subclasses = cls.__subclasses__()
    if not subclasses:  # If no subclasses, it's an end class
        return [cls]
    for subclass in subclasses:
        end_classes.extend(find_end_classes(subclass))  # Recursively find end classes
    return end_classes


# List all end classes that are subclasses of BaseNode
end_classes = find_end_classes(BaseNode)
for cls in end_classes:
    print(cls)

####Idea 3:
# select resource type: make sure new nodes are selectable
# check the resource type defined in params, make sure we can select all of them, and also that list plus the resource type that are not selectable defined in
# a list here are echo to all of the resource types

# we fine end classes from here, but do not include all of the nodes we can select resource type from

#########
# select modified: find all node types, define ways to modify each one of them in the happy path project, modify one of them,
# run select state:modified and make sure the modified node is selected
