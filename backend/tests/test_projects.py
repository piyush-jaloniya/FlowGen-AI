"""Regression fixtures that use realistic CLI and service project layouts."""

from io import BytesIO
from json import JSONDecodeError
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.tsconfig import read_jsonc

FIXTURES = Path(__file__).parent / "projects"


@pytest.fixture
def client():
    with TestClient(app) as session:
        yield session


def upload_fixture(client, name):
    root = FIXTURES / name
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix != ".pyc":
                archive.write(path, name + "/" + path.relative_to(root).as_posix())
    response = client.post("/api/upload", files={"files": (name + ".zip", stream.getvalue())})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["diagnostics"] == [], data
    return data


def edges(graph, kind):
    nodes = {node["id"]: node for node in graph["nodes"]}
    return {
        (
            (nodes[item["source"]]["path"], nodes[item["source"]]["label"]),
            (nodes[item["target"]]["path"], nodes[item["target"]]["label"]),
        )
        for item in graph["edges"]
        if item["kind"] == kind
    }


def analyze(client, files, mode="workflow", symbol=None):
    response = client.post(
        "/api/analyze",
        json={
            "files": files,
            "mode": mode,
            "symbolId": symbol,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def unit(path, source):
    return {"path": path, "content": source}


def test_commonjs_cli_tracks_calls_and_preserves_callback_uncertainty(client):
    report = upload_fixture(client, "commonjs_cli")
    graph = report["graph"]
    assert graph["title"] == "Main"
    assert edges(graph, "call") == {
        (("bin/cli.cjs", "Main"), ("src/audit.cjs", "Record")),
        (("bin/cli.cjs", "Main"), ("src/commands.cjs", "Run")),
        (("src/commands.cjs", "Run"), ("src/flags.cjs", "Parse Args")),
        (("src/commands.cjs", "Run"), ("src/audit.cjs", "Record")),
    }
    assert (("bin/cli.cjs", "Main"), ("bin/cli.cjs", "Handle Job")) in edges(graph, "external")
    overview = analyze(client, report["files"], "overview")["graph"]
    assert (("bin/cli.cjs", "bin/cli.cjs"), ("src/commands.cjs", "src/commands.cjs")) in edges(
        overview, "dependency"
    )


def test_python_service_traces_route_into_package_and_opens_flowchart(client):
    report = upload_fixture(client, "python_service")
    graph = report["graph"]
    assert graph["title"] == "Checkout"
    assert edges(graph, "call") == {
        (("shop/routes.py", "Checkout"), ("shop/payments.py", "Calculate total")),
        (("shop/payments.py", "Calculate total"), ("shop/repository.py", "Unit price")),
    }
    target = next(node["symbolId"] for node in graph["nodes"] if node["label"] == "Calculate total")
    detail = analyze(client, report["files"], "flowchart", target)["graph"]
    assert {node["kind"] for node in detail["nodes"]} >= {"decision", "end", "control"}


def test_typescript_project_roundtrips_inherited_config_and_reexports(client):
    report = upload_fixture(client, "typescript_web")
    assert {item["path"] for item in report["files"] if item["language"] == "config"} == {
        "tsconfig.json",
        "tsconfig.base.json",
    }
    expected = {
        (("src/server.ts", "Main"), ("src/checkout/order.ts", "Order")),
        (("src/checkout/order.ts", "Order"), ("src/checkout/pricing/index.ts", "Unit Price")),
    }
    assert edges(report["graph"], "call") == expected
    graph = analyze(client, report["files"], "workflow", report["graph"]["symbolId"])["graph"]
    assert edges(graph, "call") == expected
    overview = analyze(client, report["files"], "overview")["graph"]
    assert not any(node["path"].endswith(".json") for node in overview["nodes"])


@pytest.mark.parametrize("extension", ["js", "ts"])
def test_calls_respect_block_parameters_destructuring_and_closures(client, extension):
    source = """
function save() {}
function outer({ save }) {
  function closure() { save(); }
  closure();
}
function main() {
  { const { save } = factory(); save(); }
  save();
  try { work(); } catch (save) { save(); }
  for (const save of items) save();
  outer({});
}
"""
    graph = analyze(client, [unit(f"entry.{extension}", source)])["graph"]
    by_id = {node["id"]: node for node in graph["nodes"]}
    resolved = [
        (by_id[e["source"]]["label"], by_id[e["target"]]["label"], e["label"])
        for e in graph["edges"]
        if e["kind"] == "call"
    ]
    assert resolved == [
        ("Main", "Save", "L9"),
        ("Main", "Outer", "L12"),
        ("Outer", "Closure", "L5"),
    ]
    assert (("entry." + extension, "Closure"), ("entry." + extension, "Save")) in edges(
        graph, "external"
    )


def test_explicit_imports_do_not_resolve_private_or_type_only_values(client):
    report = analyze(
        client,
        [
            unit(
                "entry.ts",
                """
import { privateFn, type typeOnly, publicFn as renamed } from "./module";
function main() { privateFn(); typeOnly(); renamed(); }
""",
            ),
            unit(
                "module.ts",
                "function privateFn() {} export function typeOnly() {} export function publicFn() {}",
            ),
        ],
    )
    graph = report["graph"]
    assert edges(graph, "call") == {(("entry.ts", "Main"), ("module.ts", "Public Fn"))}
    assert {node["label"] for node in graph["nodes"] if node["kind"] == "external"} >= {
        "Private Fn",
        "Type Only",
    }


def test_circular_or_ambiguous_barrels_are_bounded(client):
    report = analyze(
        client,
        [
            unit(
                "entry.js",
                "import { run, only } from './barrel.js'; function main(){ run(); only(); }",
            ),
            unit("barrel.js", "export * from './a.js'; export * from './b.js';"),
            unit(
                "a.js",
                "export * from './barrel.js'; export function run() {} export function only() {}",
            ),
            unit("b.js", "export function run() {}"),
        ],
    )
    graph = report["graph"]
    assert edges(graph, "call") == {(("entry.js", "Main"), ("a.js", "Only"))}
    assert any(
        "Multiple possible exported targets" in (node["detail"] or "") for node in graph["nodes"]
    )


def test_static_class_import_and_commonjs_forwarder(client):
    report = analyze(
        client,
        [
            unit(
                "index.js",
                """
import Runner from "./runner.js";
const worker = require("./forward.cjs");
function main() { Runner.start(); worker.run(); }
""",
            ),
            unit("runner.js", "export default class Runner { static start(){} stop(){} }"),
            unit("forward.cjs", "module.exports = require('./worker.cjs');"),
            unit("worker.cjs", "exports.run = function run() {};"),
        ],
    )
    assert edges(report["graph"], "call") == {
        (("index.js", "Main"), ("runner.js", "Start")),
        (("index.js", "Main"), ("worker.cjs", "Run")),
    }


def test_malformed_nearest_config_reports_source_line(client):
    report = analyze(
        client,
        [
            unit("app/tsconfig.json", '{\n  "compilerOptions": }\n'),
            unit("app/index.ts", "function main() { task(); }"),
        ],
    )
    assert report["diagnostics"][0]["path"] == "app/tsconfig.json"
    assert report["diagnostics"][0]["line"] == 2
    assert report["graph"]["title"] == "Main"


def test_malformed_nested_config_does_not_use_parent_aliases(client):
    report = analyze(
        client,
        [
            unit("tsconfig.json", '{"compilerOptions":{"paths":{"@task":["./task.ts"]}}}'),
            unit("child/tsconfig.json", "{"),
            unit("child/entry.ts", 'import { run } from "@task"; function main(){run();}'),
            unit("task.ts", "export function run() {}"),
        ],
    )
    assert not edges(report["graph"], "call")
    assert report["diagnostics"][0]["path"] == "child/tsconfig.json"


def test_cyclic_config_cannot_leak_inherited_aliases(client):
    report = analyze(
        client,
        [
            unit("tsconfig.json", '{"extends":"./tsconfig.base"}'),
            unit(
                "tsconfig.base.json",
                '{"extends":"./tsconfig","compilerOptions":{"paths":{"@task":["./task.ts"]}}}',
            ),
            unit("entry.ts", 'import { run } from "@task"; function main(){run();}'),
            unit("task.ts", "export function run() {}"),
        ],
    )
    assert not edges(report["graph"], "call")
    assert "cyclic" in report["diagnostics"][0]["message"]


def test_calls_before_variable_initialization_and_class_getters_stay_unresolved(client):
    report = analyze(
        client,
        [
            unit(
                "main.js",
                """
import Box from './box.js';
function main() {
  run();
  const run = () => {};
  run();
  Box.inspect();
  new Box();
}
""",
            ),
            unit(
                "box.js",
                "export default class Box { constructor(){} static get inspect(){ return unknown; } }",
            ),
        ],
    )
    graph = report["graph"]
    assert edges(graph, "call") == {
        (("main.js", "Main"), ("main.js", "Run")),
        (("main.js", "Main"), ("box.js", "Constructor")),
    }
    assert [item["label"] for item in graph["edges"] if item["kind"] == "call"] == ["L6", "L8"]


def test_invalid_matching_typescript_file_prevents_guessing_javascript_fallback(client):
    report = analyze(
        client,
        [
            unit("main.ts", "import { task } from './task.js'; function main(){ task(); }"),
            unit("task.ts", "export function ("),
            unit("task.js", "export function task() {}"),
        ],
    )
    assert report["diagnostics"][0]["path"] == "task.ts"
    assert not edges(report["graph"], "call")


def test_jsonc_preserves_comment_markers_and_quotes_inside_strings():
    result = read_jsonc(
        r"""{
          "items": ["https://app.example/path", "/*value*/", "a\"b",],
          /* Keep this on the same source lines. */
        }"""
    )
    assert result["items"] == ["https://app.example/path", "/*value*/", 'a"b']
    with pytest.raises(JSONDecodeError):
        read_jsonc('{"options": {}, /* unterminated')


def test_named_class_expression_keeps_its_constructor_binding_local(client):
    report = analyze(
        client,
        [
            unit(
                "main.js",
                """
import { Worker } from './worker.js';
const Local = class Worker {
  constructor() {}
  static run() { return new Worker(); }
};
function main() { Local.run(); return new Worker(); }
""",
            ),
            unit("worker.js", "export class Worker { constructor() {} }"),
        ],
    )
    assert edges(report["graph"], "call") == {
        (("main.js", "Main"), ("main.js", "Run")),
        (("main.js", "Run"), ("main.js", "Constructor")),
        (("main.js", "Main"), ("worker.js", "Constructor")),
    }


@pytest.mark.parametrize("target", ["order.service.js", "order.service/index.js"])
def test_commonjs_resolves_dotted_filenames_and_directories(client, target):
    report = analyze(
        client,
        [
            unit(
                "main.cjs",
                """
const { place } = require('./order.service');
function main() { place(); }
""",
            ),
            unit(target, "exports.place = function place() {};"),
        ],
    )
    assert edges(report["graph"], "call") == {
        (("main.cjs", "Main"), (target, "Place")),
    }
    overview = analyze(client, report["files"], "overview")["graph"]
    assert edges(overview, "dependency") == {
        (("main.cjs", "main.cjs"), (target, target)),
    }


@pytest.mark.parametrize("specifier", ["./order.service", "@services/order.service"])
def test_typescript_resolves_dotted_imports_and_dependencies(client, specifier):
    report = analyze(
        client,
        [
            unit(
                "src/main.ts",
                f'import {{ place }} from "{specifier}"; function main(){{ place(); }}',
            ),
            unit("src/order.service.ts", "export function place() {}"),
            unit("tsconfig.json", '{"compilerOptions":{"paths":{"@services/*":["./src/*"]}}}'),
        ],
    )
    assert edges(report["graph"], "call") == {
        (("src/main.ts", "Main"), ("src/order.service.ts", "Place")),
    }
    overview = analyze(client, report["files"], "overview")["graph"]
    assert edges(overview, "dependency") == {
        (("src/main.ts", "src/main.ts"), ("src/order.service.ts", "src/order.service.ts")),
    }


@pytest.mark.parametrize(
    "expression",
    [
        "[process() for process, *rest in items]",
        "{process() for process in items}",
        "{item: process() for process, item in items}",
        "(process() for process in items)",
    ],
)
def test_python_comprehension_targets_shadow_imports(client, expression):
    report = analyze(
        client,
        [
            unit(
                "main.py",
                f"from jobs import process\n\ndef main(items):\n    return {expression}\n",
            ),
            unit("jobs.py", "def process():\n    return 1\n"),
        ],
    )
    graph = report["graph"]
    assert not edges(graph, "call")
    external = next(node for node in graph["nodes"] if node["kind"] == "external")
    assert external["detail"] == "process · Name is bound by a comprehension"


def test_python_first_iterable_uses_enclosing_scope(client):
    report = analyze(
        client,
        [
            unit(
                "main.py",
                """from jobs import process

def main():
    return [
        process()
        for process in process()
        if process()
    ]
""",
            ),
            unit("jobs.py", "def process():\n    return []\n"),
        ],
    )
    graph = report["graph"]
    assert [edge["label"] for edge in graph["edges"] if edge["kind"] == "call"] == ["L6"]
    assert [edge["label"] for edge in graph["edges"] if edge["kind"] == "external"] == [
        "L5",
        "L7",
    ]


def test_python_lambda_creation_resolves_defaults_but_skips_deferred_body(client):
    report = analyze(
        client,
        [
            unit(
                "main.py",
                """from jobs import load_default, task

def main():
    callback = lambda data=load_default(): task(data)
    return callback
""",
            ),
            unit("jobs.py", "def load_default(): return 1\ndef task(data): return data\n"),
        ],
    )
    assert edges(report["graph"], "call") == {
        (("main.py", "Main"), ("jobs.py", "Load default")),
    }


def test_python_direct_lambda_invocation_resolves_body_with_local_parameters(client):
    report = analyze(
        client,
        [
            unit(
                "main.py",
                """from jobs import task, direct

def main(callback):
    (lambda task: task())(callback)
    return (lambda: direct())()
""",
            ),
            unit("jobs.py", "def task(): return 1\ndef direct(): return 2\n"),
        ],
    )
    assert edges(report["graph"], "call") == {
        (("main.py", "Main"), ("jobs.py", "Direct")),
    }
    assert any(
        node["detail"] == "task · Name is bound by a lambda parameter"
        for node in report["graph"]["nodes"]
    )


@pytest.mark.parametrize(("source_extension", "header_extension"), [("c", "h"), ("cpp", "hpp")])
@pytest.mark.parametrize("implementation", ["src/worker", "engine/different_name"])
def test_c_family_resolves_headers_to_separate_implementation_directories(
    client, source_extension, header_extension, implementation
):
    source = f"pkg/src/main.{source_extension}"
    header = f"pkg/include/worker.{header_extension}"
    target = f"pkg/{implementation}.{source_extension}"
    include = f'#include "../include/worker.{header_extension}"\n'
    report = analyze(
        client,
        [
            unit(source, include + "int main(void) { return work(); }"),
            unit(header, "int work(void);"),
            unit(
                target,
                (include if implementation.startswith("engine/") else "")
                + "int work(void) { return 1; }",
            ),
            unit(f"unrelated/src/worker.{source_extension}", "int work(void) { return 2; }"),
        ],
    )
    assert edges(report["graph"], "call") == {((source, "Main"), (target, "Work"))}


def test_c_family_keeps_duplicate_unlinked_implementations_ambiguous(client):
    report = analyze(
        client,
        [
            unit("app/main.c", '#include "../headers/worker.h"\nint main(void){ return work(); }'),
            unit("headers/worker.h", "int work(void);"),
            unit("one/worker.c", "int work(void) { return 1; }"),
            unit("two/worker.c", "int work(void) { return 2; }"),
        ],
    )
    graph = report["graph"]
    assert not edges(graph, "call")
    assert any("Multiple possible targets" in (node["detail"] or "") for node in graph["nodes"])


@pytest.mark.parametrize(
    "pattern",
    [
        "callback",
        "_ as callback",
        "[*callback]",
        "{'key': value, **callback}",
        "Box(fn=callback)",
    ],
)
def test_python_match_captures_shadow_imported_functions(client, pattern):
    report = analyze(
        client,
        [
            unit(
                "main.py",
                f"""from jobs import callback

def main(value):
    match value:
        case {pattern}:
            return callback()
""",
            ),
            unit("jobs.py", "def callback(): return 1\n"),
        ],
    )
    assert not edges(report["graph"], "call")
    assert (("main.py", "Main"), ("main.py", "Callback")) in edges(report["graph"], "external")


def test_python_value_pattern_and_wildcard_do_not_shadow_imports(client):
    report = analyze(
        client,
        [
            unit(
                "main.py",
                """from jobs import callback

def main(value):
    match value:
        case State.callback:
            return callback()
        case _:
            return callback()
""",
            ),
            unit("jobs.py", "def callback(): return 1\n"),
        ],
    )
    assert edges(report["graph"], "call") == {
        (("main.py", "Main"), ("jobs.py", "Callback")),
    }


@pytest.mark.parametrize(
    ("ext", "private"),
    [
        ("c", "static int helper(int value) { return value; }"),
        ("c", "static int helper(int); int helper(int value) { return value; }"),
        ("cpp", "static int helper(int value) { return value; }"),
        ("cpp", "static int helper(int); int helper(int value) { return value; }"),
        ("cpp", "namespace { int helper(int value) { return value; } }"),
    ],
)
def test_c_family_keeps_private_definitions_within_their_translation_unit(client, ext, private):
    main = f"src/main.{ext}"
    worker = f"src/worker.{ext}"
    other = f"src/other.{ext}"
    report = analyze(
        client,
        [
            unit(main, '#include "../include/worker.h"\nint main(void) { return helper(0); }'),
            unit("include/worker.h", "int helper(int value);"),
            unit(worker, private + "\nint run(void) { return helper(1); }"),
            unit(other, "int helper(int value) { return value + 1; }"),
        ],
    )
    assert edges(report["graph"], "call") == {((main, "Main"), (other, "Helper"))}
    run = next(symbol["id"] for symbol in report["symbols"] if symbol["name"] == "run")
    internal = analyze(client, report["files"], "workflow", run)["graph"]
    assert edges(internal, "call") == {((worker, "Run"), (worker, "Helper"))}


def test_c_static_inline_in_included_header_is_visible_to_the_caller(client):
    report = analyze(
        client,
        [
            unit("main.c", '#include "helper.h"\nint main(void){ return helper(); }'),
            unit("helper.h", "static inline int helper(void){ return 1; }"),
        ],
    )
    assert edges(report["graph"], "call") == {(("main.c", "Main"), ("helper.h", "Helper"))}


def test_cpp_static_class_method_is_available_to_other_translation_units(client):
    report = analyze(
        client,
        [
            unit("main.cpp", '#include "worker.hpp"\nint main(){return Worker::run();}'),
            unit("worker.hpp", "struct Worker { static int run(){return 1;} };"),
        ],
    )
    assert edges(report["graph"], "call") == {(("main.cpp", "Main"), ("worker.hpp", "Run"))}


def test_c_private_definition_remains_unresolved_without_an_external_replacement(client):
    report = analyze(
        client,
        [
            unit("main.c", "extern int helper(void); int main(void){ return helper(); }"),
            unit("worker.c", "static int helper(void){ return 1; }"),
        ],
    )
    assert not edges(report["graph"], "call")
    assert (("main.c", "Main"), ("main.c", "Helper")) in edges(report["graph"], "external")


def test_cpp_static_prototype_does_not_hide_a_public_overload(client):
    report = analyze(
        client,
        [
            unit("main.cpp", "int helper(double); int main(){return helper(2.0);}"),
            unit(
                "worker.cpp",
                """
static int helper(int);
int helper(int n){return n;}
int helper(double n){return 3;}
""",
            ),
        ],
    )
    graph = report["graph"]
    assert edges(graph, "call") == {(("main.cpp", "Main"), ("worker.cpp", "Helper"))}
    helper = next(node for node in graph["nodes"] if node["kind"] == "call")
    assert helper["line"] == 4
