"""Exercise the workbench in Chromium using the real FastAPI responses."""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from socket import socket
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn
from playwright.sync_api import expect, sync_playwright

from backend.app.main import app

from .test_uploads import archive


@pytest.fixture(scope="module")
def origin():
    with socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        thread = Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 10
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(0.025)
            assert server.started
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            thread.join(10)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        channel = os.environ.get("FLOWGEN_CHROMIUM_CHANNEL")
        with playwright.chromium.launch(channel=channel, args=["--no-proxy-server"]) as instance:
            yield instance


@pytest.fixture
def page(browser, origin):
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    tab = context.new_page()
    failures = []
    tab.on("pageerror", lambda error: failures.append(str(error)))
    tab.on(
        "console",
        lambda item: failures.append(item.text) if "Content Security Policy" in item.text else None,
    )
    try:
        tab.goto(origin)
        expect(tab.locator("#graph svg")).to_have_attribute("aria-label", "Calculate total")
        yield tab
    finally:
        context.close()
    assert not failures, failures


def test_default_example_keyboard_source_controls_and_exports(page, tmp_path):
    canvas = page.locator("#graph svg")
    decision = page.get_by_role("button", name="member, snippet.py, line 3")
    expect(page.locator("#highlight .token-keyword").first).to_have_text("def")
    decision.focus()
    decision.press("Enter")
    expect(page.locator("#source-preview")).to_contain_text("member")
    page.get_by_role("button", name="Close step details").click()
    expect(decision).to_be_focused()

    width = int(canvas.get_attribute("width"))
    page.get_by_role("button", name="Zoom in").click()
    assert int(canvas.get_attribute("width")) > width
    page.get_by_role("button", name="Zoom out").click()
    page.get_by_role("button", name="Fit diagram").click()
    page.get_by_role("button", name="Expand diagram").click()
    expect(page.locator("#diagram-panel")).to_have_class("panel diagram-panel expanded")
    page.keyboard.press("Escape")
    expect(page.locator("#diagram-panel")).to_have_class("panel diagram-panel")

    for label, suffix in [
        ("SVG image", "svg"),
        ("PNG image", "png"),
        ("Graph JSON", "json"),
        ("Mermaid source", "mmd"),
    ]:
        page.locator("#export-toggle").click()
        with page.expect_download() as contained:
            page.get_by_role("button", name=label).click()
        download = contained.value
        destination = tmp_path / download.suggested_filename
        download.save_as(destination)
        assert destination.suffix == "." + suffix
        if suffix == "svg":
            assert ET.parse(destination).getroot().tag == "{http://www.w3.org/2000/svg}svg"
        elif suffix == "png":
            assert destination.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        elif suffix == "json":
            assert json.loads(destination.read_text(encoding="utf-8"))["mode"] == "flowchart"
        else:
            assert destination.read_text(encoding="utf-8").startswith("flowchart TD\n")


def test_sample_project_module_view_and_drilldown(page):
    page.get_by_role("button", name="Try a sample project").click()
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "Main")
    expect(page.locator("#upload-summary")).to_have_text("3 selected")
    viewbox = page.locator("#graph svg").get_attribute("viewBox")
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator("#graph svg")).not_to_have_attribute("viewBox", viewbox)
    page.set_viewport_size({"width": 1440, "height": 1000})
    expect(page.locator("#graph svg")).to_have_attribute("viewBox", viewbox)
    page.get_by_role("button", name="Modules", exact=True).click()
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "Project modules")
    expect(page.locator("#graph-count")).to_contain_text("3 modules")
    page.get_by_role("button", name="Workflow", exact=True).click()
    step = page.get_by_role("button", name="Calculate total, billing.py, line 1")
    step.click()
    expect(page.locator("#step-location")).to_contain_text("billing.py:1")
    page.get_by_role("button", name="Open flowchart").click()
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "Calculate total")
    expect(page.get_by_role("button", name="Flowchart", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )


def test_invalid_code_language_selection_and_recovery(page):
    page.get_by_label("Source code").fill("def (")
    page.get_by_role("button", name="Generate diagram").click()
    expect(page.locator("#messages")).to_contain_text("Could not parse this code")
    expect(page.locator("#graph svg")).to_have_count(0)
    page.get_by_label("Language", exact=True).select_option("typescript")
    page.get_by_role("button", name="Load example").click()
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "Calculate Total")
    expect(page.locator("#filename")).to_have_text("snippet.ts")
    expect(page.locator("#messages")).to_be_hidden()


def test_file_upload_and_zip(page):
    page.get_by_role("button", name="Files or project").click()
    page.locator("#file-input").set_input_files(
        {
            "name": "tool.py",
            "mimeType": "text/plain",
            "buffer": b"def main():\n    print('hi')\n",
        }
    )
    expect(page.locator("#file-list")).to_contain_text("tool.py")
    page.get_by_role("button", name="Generate diagram").click()
    expect(page.get_by_role("button", name="Flowchart", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(page.get_by_role("button", name="Start · Main, tool.py, line 1")).to_be_visible()
    page.get_by_role("button", name="Workflow", exact=True).click()
    expect(page.get_by_role("button", name="Print, tool.py, line 2")).to_be_visible()

    page.locator("#file-input").set_input_files(
        {
            "name": "project.zip",
            "mimeType": "application/zip",
            "buffer": archive(
                {"demo/app.py": "def main():\n    checkout()\n\ndef checkout(): pass\n"}
            ),
        }
    )
    page.get_by_role("button", name="Generate diagram").click()
    expect(page.get_by_role("button", name="Checkout, app.py, line 4")).to_be_visible()


def test_folder_upload_and_mobile_layout(page, tmp_path):
    project = Path(tmp_path) / "project"
    project.mkdir()
    (project / "a.py").write_text(
        "from b import helper\n\ndef main():\n    helper()\n", encoding="utf-8"
    )
    (project / "b.py").write_text("def helper(): pass\n", encoding="utf-8")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Files or project").click()
    page.locator("#folder-input").set_input_files(project)
    expect(page.locator("#file-list")).to_contain_text("project/b.py")
    page.get_by_role("button", name="Generate diagram").click()
    expect(page.get_by_role("button", name="Helper, b.py, line 1")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_drag_and_drop_and_keyboard_submit(page):
    editor = page.get_by_label("Source code")
    editor.fill("def keyboard_submit():\n    return 7\n")
    editor.press("Control+Enter")
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "Keyboard submit")
    page.get_by_role("button", name="Files or project").click()
    data = page.evaluate_handle("""() => {
        const data = new DataTransfer();
        data.items.add(new File(['int from_drop(void) { return 7; }'], 'demo.c'));
        return data;
    }""")
    page.locator("#drop-zone").dispatch_event("drop", {"dataTransfer": data})
    expect(page.locator("#file-list")).to_contain_text("demo.c")
    page.get_by_role("button", name="Generate diagram").click()
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "From drop")


def test_typescript_configuration_is_kept_on_folder_upload_and_redraw(page):
    project = Path(__file__).parent / "projects" / "typescript_web"
    page.get_by_role("button", name="Files or project").click()
    page.locator("#folder-input").set_input_files(project)
    expect(page.locator("#file-list")).to_contain_text("typescript_web/tsconfig.base.json")
    page.get_by_role("button", name="Generate diagram").click()
    target = page.get_by_role("button", name="Order, src/checkout/order.ts, line 3")
    expect(target).to_be_visible()
    target.click()
    page.get_by_role("button", name="Open flowchart").click()
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "Order")
    page.get_by_role("button", name="Workflow", exact=True).click()
    expect(target).to_be_visible()


def test_navigation_cannot_replace_a_fresh_analysis_with_the_previous_report(page):
    diagram = page.locator("#graph svg")
    held = []
    page.route("**/api/analyze", lambda route: held.append(route))
    page.get_by_label("Source code").fill("def new_input():\n    return 5\n")
    with page.expect_request("**/api/analyze"):
        page.get_by_role("button", name="Generate diagram").click()
    workflow = page.get_by_role("button", name="Workflow", exact=True)
    expect(workflow).to_be_disabled()
    expect(page.get_by_label("Diagram scope")).to_be_disabled()
    workflow.dispatch_event("click")
    expect(page.locator("#diagram-panel")).to_have_attribute("aria-busy", "true")
    assert len(held) == 1
    held[0].continue_()
    page.unroute("**/api/analyze")
    expect(diagram).to_have_attribute("aria-label", "New input")
    expect(workflow).to_be_enabled()
    workflow.click()
    expect(workflow).to_have_attribute("aria-pressed", "true")
    expect(diagram).to_have_attribute("aria-label", "Top-level code")


def test_directory_upload_ignores_nested_archives(page, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("def main():\n    return 5\n", encoding="utf-8")
    (project / "assets").mkdir()
    (project / "assets" / "fixture.zip").write_bytes(archive({"example.py": "x = 1"}))
    page.get_by_role("button", name="Files or project").click()
    page.locator("#folder-input").set_input_files(project)
    expect(page.locator("#upload-summary")).to_have_text("1 selected · 1 skipped")
    page.get_by_role("button", name="Generate diagram").click()
    expect(page.locator("#graph svg")).to_have_attribute("aria-label", "Main")


def test_failed_scope_and_view_changes_preserve_the_displayed_diagram(page):
    editor = page.get_by_label("Source code")
    editor.fill("def small():\n    return 1\n\ndef large():\n" + "    x = 1\n" * 310)
    page.get_by_role("button", name="Generate diagram").click()
    diagram = page.locator("#graph svg")
    expect(diagram).to_have_attribute("aria-label", "Small")
    scope = page.get_by_label("Diagram scope")
    small = scope.input_value()
    scope.select_option(label="Large · snippet.py:4")
    expect(page.locator("#messages")).to_contain_text("Diagram exceeds 300 nodes")
    expect(scope).to_have_value(small)
    expect(diagram).to_have_attribute("aria-label", "Small")
    expect(page.locator("#export-toggle")).to_be_enabled()

    page.route(
        "**/api/analyze",
        lambda route: route.fulfill(status=503, json={"detail": "Analysis is busy."}),
    )
    page.get_by_role("button", name="Workflow", exact=True).click()
    expect(page.locator("#messages")).to_contain_text("Analysis is busy.")
    expect(page.get_by_role("button", name="Flowchart", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(scope).to_have_value(small)
    expect(diagram).to_have_attribute("aria-label", "Small")


def test_view_without_graph_preserves_workflow_and_reports_diagnostics(page):
    page.get_by_role("button", name="Files or project").click()
    page.locator("#file-input").set_input_files(
        [
            {
                "name": "main.py",
                "mimeType": "text/plain",
                "buffer": ("def main():\n" + "    x = 1\n" * 310).encode("utf-8"),
            },
            {"name": "helper.py", "mimeType": "text/plain", "buffer": b"def helper(): pass\n"},
        ]
    )
    page.get_by_role("button", name="Generate diagram").click()
    diagram = page.locator("#graph svg")
    expect(diagram).to_have_attribute("aria-label", "Main")
    scope = page.get_by_label("Diagram scope")
    selected = scope.input_value()
    page.get_by_role("button", name="Flowchart", exact=True).click()
    expect(page.locator("#messages")).to_contain_text("Diagram exceeds 300 nodes")
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.get_by_role("button", name="Workflow", exact=True)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(scope).to_have_value(selected)
    expect(diagram).to_have_attribute("aria-label", "Main")
    expect(page.locator("#messages")).to_contain_text("Diagram exceeds 300 nodes")
    page.locator("#export-toggle").click()
    with page.expect_download() as exported:
        page.get_by_role("button", name="Graph JSON").click()
    assert json.loads(exported.value.path().read_text(encoding="utf-8"))["mode"] == "workflow"
