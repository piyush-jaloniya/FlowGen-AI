import sys
sys.path.insert(0, 'D:\\Study\\FlowGen AI\\backend')

from app.services.parser_service import ParserService

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

parser = ParserService()
result = parser.parse_code("python", "test.py", test_code)

import json
print(json.dumps(result, indent=2))
