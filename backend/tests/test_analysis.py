"""Check graph semantics at the API boundary and across language adapters."""

import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.model import humanize


@pytest.fixture
def client():
    with TestClient(app) as session:
        yield session


def file(path, code):
    return {"path": path, "content": code}


def report(client, *files, mode="flowchart", symbol=None):
    response = client.post("/api/analyze", json={"files": files, "mode": mode, "symbolId": symbol})
    assert response.status_code == 200, response.text
    data = response.json()
    if data["graph"]:
        assert_graph(data["graph"])
    return data


def assert_graph(graph):
    ids = {node["id"] for node in graph["nodes"]}
    assert len(ids) == len(graph["nodes"])
    assert all(edge["source"] in ids and edge["target"] in ids for edge in graph["edges"])
    assert all(node["endLine"] >= node["line"] > 0 for node in graph["nodes"] if node["path"])


def labels(graph):
    by_id = {node["id"]: node["label"] for node in graph["nodes"]}
    return [(by_id[e["source"]], by_id[e["target"]], e["label"]) for e in graph["edges"]]


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("calculate_total", "Calculate total"),
        ("validateHTTPToken", "Validate HTTP Token"),
        ("CSV_export", "CSV export"),
        ("validé_le_total", "Validé le total"),
    ],
)
def test_humanized_names(identifier, expected):
    assert humanize(identifier) == expected


@pytest.mark.parametrize(
    ("path", "code", "name"),
    [
        ("main.py", "def run(flag):\n    if flag:\n        return 1\n    return 2", "run"),
        ("main.js", "export function run(flag) { if (flag) return 1; return 2; }", "run"),
        (
            "main.ts",
            "const run = (flag: boolean): number => { if (flag) return 1; return 2; };",
            "run",
        ),
        (
            "Main.java",
            "class Main { int run(boolean flag) { if (flag) return 1; return 2; } }",
            "Main.run",
        ),
        ("main.c", "int run(int flag) { if (flag) return 1; return 2; }", "run"),
        (
            "main.cpp",
            "namespace Logic { int run(bool flag) { if (flag) return 1; return 2; } }",
            "Logic.run",
        ),
    ],
)
def test_flowchart_for_each_language(client, path, code, name):
    data = report(client, file(path, code))
    assert data["diagnostics"] == []
    assert name in {symbol["qualifiedName"] for symbol in data["symbols"]}
    graph = data["graph"]
    assert any(node["kind"] == "decision" for node in graph["nodes"])
    assert {edge[2] for edge in labels(graph)} >= {"True", "False", "Return"}
    assert [(start, target) for start, target, label in labels(graph) if label == "Return"] == [
        ("return 2", "End"),
        ("return 1", "End"),
    ]


def test_nested_loops_return_and_unreachable_code(client):
    code = """def run(items):
    for item in items:
        while item:
            if item == 2:
                break
            if item == 3:
                continue
            return item
            unreachable()
        if not item:
            continue
        after_inner_loop()
    return 0
"""
    graph = report(client, file("main.py", code))["graph"]
    edges = labels(graph)
    assert ("Break", "not item", "Exit loop or switch") in edges
    assert ("Continue", "item", "Next iteration") in edges
    assert ("Continue", "Next item in items?", "Next iteration") in edges
    assert ("return item", "End", "Return") in edges
    assert not any("unreachable" in node["label"].lower() for node in graph["nodes"])


def test_loop_else_break_exits_past_else(client):
    graph = report(
        client,
        file(
            "main.py",
            """def run(seq):
    for item in seq:
        if item:
            break
    else:
        did_finish()
    return 1
""",
        ),
    )["graph"]
    assert ("Break", "return 1", "Exit loop or switch") in labels(graph)
    assert ("Next item in seq?", "Did finish", "Exhausted") in labels(graph)


def test_c_loop_continue_updates_and_do_while_runs_body_first(client):
    graph = report(
        client,
        file(
            "main.c",
            """int main() {
    for (int i=0; i<10; i++) { continue; }
    do { before_check(); } while (again());
    return 0;
}""",
        ),
    )["graph"]
    edges = labels(graph)
    assert ("Continue", "i++", "Next iteration") in edges
    assert ("i++", "i<10", "") in edges
    assert ("i<10", "Before check", "False") in edges
    assert ("Before check", "(again())", "") in edges


def test_conditional_chain_and_match_are_distinct(client):
    graph = report(
        client,
        file(
            "main.py",
            """def run(value):
    if value == 1:
        return "one"
    elif value == 2:
        return "two"
    match value:
        case 3 if enabled():
            return "three"
        case _:
            return "other"
""",
        ),
    )["graph"]
    edges = labels(graph)
    assert ("value == 1", "value == 2", "False") in edges
    assert ("Case 3 if enabled()", "Case _", "No match") in edges
    assert ("Case _", 'return "other"', "Match") in edges


def test_finally_cleans_up_return(client):
    graph = report(
        client,
        file(
            "main.py",
            """def run():
    try:
        return try_value()
    except:
        return fallback()
    finally:
        clean_up()
""",
        ),
    )["graph"]
    edges = labels(graph)
    assert ("return try_value()", "Clean up", "Return") in edges
    assert ("return fallback()", "Clean up", "Return") in edges
    assert ("Clean up", "End", "") in edges
    assert not any(label == "Uncaught" for _, _, label in edges)


def test_js_switch_separates_fallthrough_and_break(client):
    graph = report(
        client,
        file(
            "main.js",
            """function run(x) {
    switch (x) {
      case 1: one();
      case 2: two(); break;
      default: other();
    }
    finish();
}""",
        ),
    )["graph"]
    edges = labels(graph)
    assert ("One", "case 2", "") in edges
    assert ("Break", "Finish", "Exit loop or switch") in edges
    assert ("Switch (x)", "default", "default") in edges


@pytest.mark.parametrize(
    ("files", "entry", "target", "unknown"),
    [
        (
            [
                file(
                    "pkg/main.py",
                    "from .worker import run_task as run\n\ndef main():\n    run()\n    print('ok')\n",
                ),
                file("pkg/worker.py", "def run_task():\n    pass\n"),
                file("pkg/__init__.py", '"""Package."""\n'),
            ],
            "Main",
            "Run task",
            "Print",
        ),
        (
            [
                file(
                    "main.js",
                    "import { runTask as run } from './worker.js';\nfunction main() { run(); console.log('ok'); }",
                ),
                file("worker.js", "export function runTask() {}"),
            ],
            "Main",
            "Run Task",
            "Log",
        ),
        (
            [
                file(
                    "main.ts",
                    "import * as actions from './worker.js';\nfunction main() { actions.runTask(); log(); }",
                ),
                file("worker.ts", "export const runTask = () => true;"),
            ],
            "Main",
            "Run Task",
            "Log",
        ),
        (
            [
                file(
                    "Main.java",
                    "package app; class Main { static void main(String[] args) { Worker.runTask(); log(); } }",
                ),
                file("Worker.java", "package app; class Worker { static void runTask() {} }"),
            ],
            "Main",
            "Run Task",
            "Log",
        ),
        (
            [
                file(
                    "main.c", '#include "worker.h"\nint main() { run_task(); unknown(); return 0; }'
                ),
                file("worker.h", "void run_task(void);"),
                file("worker.c", '#include "worker.h"\nvoid run_task(void) {}'),
            ],
            "Main",
            "Run task",
            "Unknown",
        ),
        (
            [
                file(
                    "main.cpp", '#include "worker.hpp"\nint main() { kit::runTask(); unknown(); }'
                ),
                file("worker.hpp", "namespace kit { void runTask(); }"),
                file("worker.cpp", "namespace kit { void runTask() {} }"),
            ],
            "Main",
            "Run Task",
            "Unknown",
        ),
    ],
)
def test_workflow_resolves_cross_file_calls(client, files, entry, target, unknown):
    data = report(client, *files, mode="workflow")
    assert not data["diagnostics"], data
    graph = data["graph"]
    assert graph["title"] == entry
    assert any(node["kind"] == "call" and node["label"] == target for node in graph["nodes"])
    assert any(node["kind"] == "external" and node["label"] == unknown for node in graph["nodes"])
    assert all(node["symbolId"] for node in graph["nodes"] if node["kind"] in {"start", "call"})
    function = next(node for node in graph["nodes"] if node["label"] == target)
    drilldown = report(client, *files, mode="flowchart", symbol=function["symbolId"])
    assert drilldown["graph"]["title"] == target


def test_dynamic_and_ambiguous_targets_remain_unresolved(client):
    source = file(
        "main.py", "def work():\n    return 1\n\ndef main(work):\n    work()\n    main(work)\n"
    )
    graph = report(client, source, mode="workflow")["graph"]
    assert any(node["label"] == "Work" and node["kind"] == "external" for node in graph["nodes"])
    assert any(
        edge["source"] == edge["target"] and edge["kind"] == "call" for edge in graph["edges"]
    )


def test_module_overview_has_dependencies_and_independent_files(client):
    files = [
        file("app.py", "import billing\n"),
        file("billing.py", "x = 1"),
        file("unrelated.py", "print(1)"),
    ]
    data = report(client, *files, mode="overview")
    assert labels(data["graph"]) == [("app.py", "billing.py", "Imports")]
    assert {node["label"] for node in data["graph"]["nodes"]} == {item["path"] for item in files}


def test_invalid_syntax_is_diagnostic_and_project_can_continue(client):
    invalid = file("broken.py", "def (")
    failed = report(client, invalid)
    assert failed["graph"] is None and failed["diagnostics"][0]["path"] == "broken.py"
    partial = report(client, invalid, file("good.py", "def main(): pass"), mode="workflow")
    assert partial["graph"]["title"] == "Main" and partial["diagnostics"][0]["line"] == 1


def test_unconditional_javascript_loop_has_no_false_exit(client):
    graph = report(client, file("main.js", "function main() { for (;;) { break; } done(); }"))[
        "graph"
    ]
    assert ("Repeat", "Break", "True") in labels(graph)
    assert not any(source == "Repeat" and branch == "False" for source, _, branch in labels(graph))
    assert ("Break", "Done", "Exit loop or switch") in labels(graph)


def test_java_for_loop_runs_all_updates_on_continue(client):
    graph = report(
        client,
        file(
            "Main.java",
            """class Main {
        void run() {
            for (int i = 0, j = 1; i < 10; i++, j++) { continue; }
        }
    }""",
        ),
    )["graph"]
    assert ("Continue", "i++", "Next iteration") in labels(graph)
    assert ("i++", "j++", "") in labels(graph)
    assert ("j++", "i < 10", "") in labels(graph)


def test_expression_body_returns_value_and_empty_source_is_diagnostic(client):
    graph = report(client, file("main.ts", "const run = () => 42;"))["graph"]
    assert ("Return 42", "End", "Return") in labels(graph)
    empty = report(client, file("main.py", " "))
    assert empty["graph"] is None
    assert empty["diagnostics"][0]["message"] == "No code found."


def test_typescript_parameterized_catch_only_escapes_on_explicit_rethrow(client):
    source = """
function main() {
    try { throw new Error('failed'); }
    catch (error) {
        if (shouldRethrow(error)) throw error;
        return false;
    }
}
"""
    graph = report(client, file("main.ts", source))["graph"]
    assert ("Which handler matches?", "(shouldRethrow(error))", "error") in labels(graph)
    assert not any(label == "Uncaught" for _, _, label in labels(graph))
    assert ("throw error", "Uncaught exception", "Exception") in labels(graph)


@pytest.mark.parametrize("catch_all", ["catch(...)", "catch ( /* all errors */ ... )"])
def test_cpp_ellipsis_handler_catches_all_exceptions(client, catch_all):
    source = f"int main() {{ try {{ throw 1; }} catch(int value) {{ return value; }} {catch_all} {{ return 0; }} }}"
    graph = report(client, file("main.cpp", source))["graph"]
    assert not any(label == "Uncaught" for _, _, label in labels(graph))
    assert any(
        origin == "Which handler matches?" and target == "return 0"
        for origin, target, _ in labels(graph)
    )


@pytest.mark.parametrize("separator", ["", "\n"])
def test_cpp_typed_handler_leaves_unmatched_exceptions_possible(client, separator):
    source = f"int main(){{ try {{ throw 1; }} catch{separator}(int value) {{ return value; }} }}"
    graph = report(client, file("main.cpp", source))["graph"]
    assert ("Which handler matches?", "Uncaught exception", "Uncaught") in labels(graph)


@pytest.mark.parametrize(
    ("pattern", "can_fail"),
    [
        ("value", False),
        ("(value)", False),
        ("(_ as value)", False),
        ("1 | _", False),
        ("value if allowed(value)", True),
        ("(value,)", True),
        ("[value]", True),
        ("Constants.VALUE", True),
        ("1 as value", True),
    ],
)
def test_python_match_only_falls_through_when_pattern_or_guard_can_fail(client, pattern, can_fail):
    source = f"def main(x):\n    match x:\n        case {pattern}:\n            return 1\n"
    graph = report(client, file("main.py", source))["graph"]
    assert any(label == "No match" for _, _, label in labels(graph)) is can_fail
