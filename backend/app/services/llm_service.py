import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

class LLMService:
    """
    Integrates Google Gemini API for intelligent code analysis.
    Provides smart descriptions, pattern detection, and improvement suggestions.
    """

    def __init__(self):
        # Check for Gemini API key
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        self.enabled = bool(self.api_key)
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.model = genai.GenerativeModel(self.model_name)
                self.provider = "gemini"
                print(f"✅ LLM Service: Using Google Gemini with {self.model_name}")
            except Exception as e:
                print(f"⚠️  Warning: Gemini initialization failed: {e}")
                self.enabled = False
                self.model = None
        else:
            print("ℹ️  LLM Service: No Gemini API key found. AI features disabled.")
            print("   Get free Gemini API key: https://aistudio.google.com/app/apikey")
            self.model = None
            self.provider = None

    def is_enabled(self) -> bool:
        """Check if LLM service is available."""
        return self.enabled

    def analyze_code_snippet(self, code: str, language: str) -> Optional[str]:
        """
        Analyze a code snippet and generate a detailed line-by-line explanation.
        
        Args:
            code: The source code to analyze
            language: Programming language (python, javascript, etc.)
        
        Returns:
            A comprehensive line-by-line breakdown of the code
        """
        if not self.enabled or not self.model:
            return None

        try:
            prompt = f"""Provide a detailed code explanation in the following format:

Break down this {language} code into logical blocks. For each block:

**Code Block:**
```
[Show the code block here]
```

**Explanation:**
[Provide a detailed explanation of what this code does, why it's needed, and any important details about data types, logic, or edge cases]

Continue this pattern for all significant blocks in the code. Make it educational and easy to understand.

Code to analyze:
```{language}
{code}
```

Detailed Explanation:"""

            print(f"🔍 Sending request to Gemini for detailed analysis...")
            response = self.model.generate_content(prompt)
            print(f"✅ Gemini response received: {response.text[:100]}...")
            return response.text.strip()
        except Exception as e:
            print(f"⚠️  Gemini analysis error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def detect_algorithm_pattern(self, code: str, language: str) -> Optional[str]:
        """
        Detect common algorithm patterns (sorting, searching, etc.).
        
        Args:
            code: The source code
            language: Programming language
        
        Returns:
            Algorithm pattern name or None
        """
        if not self.enabled or not self.model:
            return None

        try:
            prompt = f"""Identify the main algorithm pattern used in this code.
Respond with ONLY ONE of these: Sorting, Searching, Recursion, Dynamic Programming, Greedy, Backtracking, Divide and Conquer, Graph Algorithm, String Manipulation, Data Structure Operation, Mathematical Computation, I/O Operation, or None.

Code:
```{language}
{code}
```

Pattern:"""

            response = self.model.generate_content(prompt)
            pattern = response.text.strip()
            return pattern if pattern != "None" else None
        except Exception as e:
            print(f"⚠️  Gemini pattern detection error: {e}")
            return None

    def suggest_improvements(self, code: str, language: str) -> Optional[str]:
        """
        Suggest code improvements with actual improved code.
        
        Args:
            code: The source code
            language: Programming language
        
        Returns:
            String containing improvements with improved code
        """
        if not self.enabled or not self.model:
            return None

        try:
            prompt = f"""Analyze this {language} code and provide improvements in the following format:

**Improvement 1: [Brief title]**
**What to improve:** [Brief explanation]
**Improved Code:**
```{language}
[Show the improved code here]
```

**Improvement 2: [Brief title]**
**What to improve:** [Brief explanation]
**Improved Code:**
```{language}
[Show the improved code here]
```

Provide 2-3 improvements focusing on: readability, performance, error handling, or best practices.

Original Code:
```{language}
{code}
```

Code Improvements:"""

            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"⚠️  Gemini suggestion error: {e}")
            return None
