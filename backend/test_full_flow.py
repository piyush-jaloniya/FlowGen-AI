import sys
sys.path.insert(0, 'D:\\Study\\FlowGen AI\\backend')

from app.services.parser_service import ParserService
from app.services.flowchart_service import FlowchartService
from app.services.workflow_service import WorkflowService

# Test code
test_code = """def calculate_grade(score):
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"
"""

print("=" * 80)
print("TESTING PARSER")
print("=" * 80)
parser = ParserService()
parsed = parser.parse_code("python", "test.py", test_code)
print(f"Parser result has {len(parsed.get('functions', []))} functions")
if parsed.get('functions'):
    func = parsed['functions'][0]
    print(f"Function name: {func['name']}")
    print(f"Has body: {bool(func.get('body'))}")
    if func.get('body'):
        print(f"Body has {len(func['body'])} statements")

print("\n" + "=" * 80)
print("TESTING FLOWCHART")
print("=" * 80)
flowchart_service = FlowchartService()
flowchart = flowchart_service.build(parsed)
if 'error' in flowchart:
    print(f"ERROR: {flowchart['error']}")
else:
    print("Flowchart generated successfully!")
    print(f"Mermaid code length: {len(flowchart.get('mermaid', ''))}")
    print("\nFirst 500 chars of mermaid:")
    print(flowchart.get('mermaid', '')[:500])

print("\n" + "=" * 80)
print("TESTING WORKFLOW")
print("=" * 80)
workflow_service = WorkflowService()
workflow = workflow_service.build(parsed)
if 'error' in workflow:
    print(f"ERROR: {workflow['error']}")
else:
    print("Workflow generated successfully!")
    print(f"Mermaid code length: {len(workflow.get('mermaid', ''))}")
    print("\nFirst 500 chars of mermaid:")
    print(workflow.get('mermaid', '')[:500])
