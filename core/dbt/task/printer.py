from typing import Dict, Optional

from dbt.artifacts.schemas.results import NodeStatus
from dbt.contracts.graph.nodes import Group
from dbt.events.types import (
    CheckNodeTestFailure,
    EndOfRunSummary,
    RunResultError,
    RunResultErrorNoMessage,
    RunResultFailure,
    RunResultWarning,
    RunResultWarningMessage,
    SQLCompiledPath,
    StatsLine,
)
from dbt.node_types import NodeType
from dbt_common.events.base_types import EventLevel
from dbt_common.events.format import pluralize
from dbt_common.events.functions import fire_event
from dbt_common.events.types import Formatting


def get_counts(flat_nodes) -> str:
    counts: Dict[str, int] = {}

    for node in flat_nodes:
        t = node.resource_type

        if node.resource_type == NodeType.Model:
            t = "{} {}".format(node.get_materialization(), t)
        elif node.resource_type == NodeType.Operation:
            t = "project hook"

        counts[t] = counts.get(t, 0) + 1

    stat_line = ", ".join([pluralize(v, k).replace("_", " ") for k, v in counts.items()])

    return stat_line


def interpret_run_result(result) -> str:
    if result.status in (NodeStatus.Error, NodeStatus.Fail):
        return "error"
    elif result.status == NodeStatus.Skipped:
        return "skip"
    elif result.status == NodeStatus.Warn:
        return "warn"
    elif result.status in (NodeStatus.Pass, NodeStatus.Success):
        return "pass"
    else:
        raise RuntimeError(f"unhandled result {result}")


def print_run_status_line(results) -> None:
    stats = {
        "error": 0,
        "skip": 0,
        "pass": 0,
        "warn": 0,
        "total": 0,
    }

    for r in results:
        result_type = interpret_run_result(r)
        stats[result_type] += 1
        stats["total"] += 1

    fire_event(Formatting(""))
    fire_event(StatsLine(stats=stats))


def print_run_result_error(
    result, newline: bool = True, is_warning: bool = False, group: Optional[Group] = None
) -> None:
    # set node_info for logging events
    node_info = None
    if hasattr(result, "node") and result.node:
        node_info = result.node.node_info
    if result.status == NodeStatus.Fail or (is_warning and result.status == NodeStatus.Warn):
        if newline:
            fire_event(Formatting(""))
        if is_warning:
            group_dict = group.to_logging_dict() if group else None
            fire_event(
                RunResultWarning(
                    resource_type=result.node.resource_type,
                    node_name=result.node.name,
                    path=result.node.original_file_path,
                    node_info=node_info,
                    group=group_dict,
                )
            )
        else:
            group_dict = group.to_logging_dict() if group else None
            fire_event(
                RunResultFailure(
                    resource_type=result.node.resource_type,
                    node_name=result.node.name,
                    path=result.node.original_file_path,
                    node_info=node_info,
                    group=group_dict,
                )
            )

        if result.message:
            if is_warning:
                fire_event(RunResultWarningMessage(msg=result.message, node_info=node_info))
            else:
                group_dict = group.to_logging_dict() if group else None
                fire_event(
                    RunResultError(msg=result.message, node_info=node_info, group=group_dict)
                )
        else:
            fire_event(RunResultErrorNoMessage(status=result.status, node_info=node_info))

        if result.node.compiled_path is not None:
            fire_event(Formatting(""))
            fire_event(SQLCompiledPath(path=result.node.compiled_path, node_info=node_info))

        if result.node.should_store_failures:
            fire_event(Formatting(""))
            fire_event(
                CheckNodeTestFailure(relation_name=result.node.relation_name, node_info=node_info)
            )
    elif result.status == NodeStatus.Skipped and result.message is not None:
        if newline:
            fire_event(Formatting(""), level=EventLevel.DEBUG)
        fire_event(RunResultError(msg=result.message), level=EventLevel.DEBUG)
    elif result.message is not None:
        if newline:
            fire_event(Formatting(""))
        group_dict = group.to_logging_dict() if group else None
        fire_event(RunResultError(msg=result.message, node_info=node_info, group=group_dict))


def print_run_end_messages(
    results, keyboard_interrupt: bool = False, groups: Optional[Dict[str, Group]] = None
) -> None:
    errors, warnings = [], []
    for r in results:
        if r.status in (NodeStatus.RuntimeErr, NodeStatus.Error, NodeStatus.Fail):
            errors.append(r)
        elif r.status == NodeStatus.Skipped and r.message is not None:
            # this means we skipped a node because of an issue upstream,
            # so include it as an error
            errors.append(r)
        elif r.status == NodeStatus.Warn:
            warnings.append(r)

    fire_event(Formatting(""))
    fire_event(
        EndOfRunSummary(
            num_errors=len(errors),
            num_warnings=len(warnings),
            keyboard_interrupt=keyboard_interrupt,
        )
    )

    for error in errors:
        group = groups.get(error.node.unique_id) if groups and hasattr(error, "node") else None
        print_run_result_error(error, is_warning=False, group=group)

    for warning in warnings:
        group = groups.get(warning.node.unique_id) if groups and hasattr(warning, "node") else None
        print_run_result_error(warning, is_warning=True, group=group)

    print_run_status_line(results)
