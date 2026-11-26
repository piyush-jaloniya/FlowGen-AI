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
