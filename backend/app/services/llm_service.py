import os
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import google.generativeai as genai
from .ai_cache import AIInsightsCache, QuotaTracker
from .ai_utils import retry_with_backoff, chunk_code, get_code_metrics

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LLMService:
    """
    Integrates Google Gemini API for intelligent code analysis.
    Provides smart descriptions, pattern detection, and improvement suggestions.
    Enhanced with caching, quota tracking, retry logic, and fallbacks.
    """

    def __init__(self):
        # Check for Gemini API key
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        self.enabled = bool(self.api_key)
        
        # Initialize cache and quota tracker
        self.cache = AIInsightsCache(ttl_hours=24)
        self.quota_tracker = QuotaTracker(daily_limit=15)
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.model = genai.GenerativeModel(self.model_name)
                self.provider = "gemini"
                logger.info(f"LLM Service: Using Google Gemini with {self.model_name}")
                logger.info(f"AI Insights quota: {self.quota_tracker.get_remaining()}/15 requests remaining today")
            except Exception as e:
                logger.warning(f"Gemini initialization failed: {e}")
                self.enabled = False
                self.model = None
        else:
            logger.info("LLM Service: No Gemini API key found. AI features disabled.")
            logger.info("Get free Gemini API key: https://aistudio.google.com/app/apikey")
            self.model = None
            self.provider = None

    def is_enabled(self) -> bool:
        """Check if LLM service is available."""
        return self.enabled

    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def _call_gemini_api(self, prompt: str) -> str:
        """Call Gemini API with retry logic."""
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def _get_quota_message(self, remaining: int) -> str:
        """Generate quota exceeded message."""
        return f"""⚠️ **AI Insights Daily Limit Reached**

You've used all {self.quota_tracker.daily_limit} free AI Insights requests for today.

**Options:**
1. ⏰ Wait until tomorrow for quota reset
2. 🔑 Get a new free API key: https://aistudio.google.com/app/apikey
3. 💳 Upgrade to Gemini Pro for higher limits

**Tip:** Identical code is cached, so re-analyzing the same code won't count against your quota!"""

    def _local_analysis_fallback(self, code: str, language: str) -> str:
        """Provide basic local analysis when API is unavailable."""
        metrics = get_code_metrics(code, language)
        
        return f"""## 📊 Basic Code Analysis (Local)

**Code Statistics:**
- Total lines: {metrics['total_lines']}
- Code lines (non-empty): {metrics['code_lines']}
- Functions: {metrics['functions']}
- Classes: {metrics['classes']}
- Imports: {metrics['imports']}
- Loops: {metrics['loops']}
- Conditional statements: {metrics['conditions']}
- Cyclomatic complexity: {metrics['complexity']}

**Complexity Assessment:**
{self._get_complexity_assessment(metrics['complexity'])}

**Note:** AI-powered insights are temporarily unavailable. This is a basic static analysis.
For detailed insights, please try again later or check your API configuration."""

    def _get_complexity_assessment(self, complexity: int) -> str:
        """Get complexity assessment message."""
        if complexity <= 5:
            return "✅ **Low complexity** - Code is simple and easy to understand"
        elif complexity <= 10:
            return "⚠️ **Moderate complexity** - Code is reasonably complex"
        elif complexity <= 20:
            return "🔶 **High complexity** - Consider refactoring for better maintainability"
        else:
            return "🔴 **Very high complexity** - Strongly recommend refactoring"

    def analyze_code_snippet(self, code: str, language: str) -> Optional[str]:
        """
        Analyze a code snippet and generate a detailed explanation.
        Enhanced with caching, quota tracking, and fallbacks.
        
        Args:
            code: The source code to analyze
            language: Programming language (python, javascript, etc.)
        
        Returns:
            A comprehensive analysis of the code
        """
        if not self.enabled or not self.model:
            return self._local_analysis_fallback(code, language)

        # Check cache first
        cached_response = self.cache.get(code, 'analysis')
        if cached_response:
            logger.info("Returning cached analysis (no quota used)")
            return cached_response

        # Check quota
        can_request, remaining = self.quota_tracker.can_make_request()
        if not can_request:
            logger.warning("AI Insights quota exceeded")
            return self._get_quota_message(remaining)

        # Warn if low quota
        if remaining <= 3:
            logger.warning(f"⚠️ Low quota: Only {remaining} AI Insights requests remaining today")

        try:
            # Enhanced prompt with better structure
            prompt = f"""You are an expert {language} developer. Analyze this code comprehensively and educationally.

## 📋 Code Overview
Provide a brief 1-2 sentence summary of what this code does.

## 🔍 Detailed Breakdown

Break down the code into logical sections. For each section:

### [Section Name/Purpose]
**Code:**
```{language}
[relevant code snippet]
```

**Explanation:**
- What this code does
- Why it's needed
- Key concepts (data types, algorithms, patterns)
- Important details or edge cases

## 💡 Key Takeaways
List 2-4 important concepts or patterns demonstrated:
- [Concept 1]
- [Concept 2]
- [Concept 3]

## ⚠️ Potential Issues
Identify any bugs, inefficiencies, or areas for improvement.

---

Code to analyze:
```{language}
{code}
```

Provide your detailed analysis:"""

            logger.debug("Sending request to Gemini for detailed analysis...")
            response = self._call_gemini_api(prompt)
            
            # Cache the response
            self.cache.set(code, 'analysis', response)
            
            # Increment quota
            self.quota_tracker.increment()
            remaining_after = self.quota_tracker.get_remaining()
            logger.info(f"AI Insights used. Remaining: {remaining_after}/15")
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "ResourceExhausted" in error_msg:
                logger.warning(f"Gemini API quota exceeded: {e}")
                return "⚠️ **AI Insights Temporarily Unavailable**\\n\\nThe Gemini API free tier quota (20 requests/day) has been exceeded. Please try again later or upgrade your API key.\\n\\nGet a free API key: https://aistudio.google.com/app/apikey"
            logger.error(f"Gemini analysis error: {type(e).__name__}: {e}", exc_info=True)
            # Fallback to local analysis
            return self._local_analysis_fallback(code, language)

    def detect_algorithm_pattern(self, code: str, language: str) -> Optional[str]:
        """
        Detect common algorithm patterns with caching and quota tracking.
        
        Args:
            code: The source code
            language: Programming language
        
        Returns:
            Algorithm pattern name or None
        """
        if not self.enabled or not self.model:
            return None

        # Check cache
        cached_response = self.cache.get(code, 'pattern')
        if cached_response:
            return cached_response

        # Check quota
        can_request, remaining = self.quota_tracker.can_make_request()
        if not can_request:
            return "Quota Exceeded"

        try:
            prompt = f"""Analyze this {language} code and identify the primary algorithm/pattern.

Respond with ONE of these (be specific):
- Sorting (specify: Bubble Sort, Merge Sort, Quick Sort, etc.)
- Searching (specify: Linear Search, Binary Search, etc.)
- Recursion
- Dynamic Programming
- Greedy Algorithm
- Backtracking
- Divide and Conquer
- Graph Algorithm (specify: DFS, BFS, Dijkstra, etc.)
- String Manipulation
- Data Structure Operation
- Mathematical Computation
- I/O Operation
- None

Code:
```{language}
{code}
```

Pattern:"""

            response = self._call_gemini_api(prompt)
            pattern = response.strip()
            
            # Cache the response
            self.cache.set(code, 'pattern', pattern)
            
            # Increment quota
            self.quota_tracker.increment()
            
            return pattern if pattern != "None" else None
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "ResourceExhausted" in error_msg:
                logger.warning(f"Gemini API quota exceeded for pattern detection: {e}")
                return "Quota Exceeded"
            logger.error(f"Gemini pattern detection error: {e}")
            return None

    def suggest_improvements(self, code: str, language: str) -> Optional[str]:
        """
        Suggest code improvements with caching and quota tracking.
        
        Args:
            code: The source code
            language: Programming language
        
        Returns:
            String containing improvements with improved code
        """
        if not self.enabled or not self.model:
            return None

        # Check cache
        cached_response = self.cache.get(code, 'improvements')
        if cached_response:
            return cached_response

        # Check quota
        can_request, remaining = self.quota_tracker.can_make_request()
        if not can_request:
            return self._get_quota_message(remaining)

        try:
            prompt = f"""Analyze this {language} code and provide practical improvements.

Format each improvement as:

**Improvement [N]: [Brief Title]**
**What to improve:** [Clear explanation of the issue]
**Improved Code:**
```{language}
[Show the improved code here]
```
**Why this is better:** [Explain the benefits]

Provide 2-3 improvements focusing on:
- Code readability and clarity
- Performance optimizations
- Error handling and edge cases
- Best practices and design patterns

Original Code:
```{language}
{code}
```

Code Improvements:"""

            response = self._call_gemini_api(prompt)
            
            # Cache the response
            self.cache.set(code, 'improvements', response)
            
            # Increment quota
            self.quota_tracker.increment()
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "ResourceExhausted" in error_msg:
                logger.warning(f"Gemini API quota exceeded for suggestions: {e}")
                return "⚠️ **Improvement Suggestions Unavailable**\\n\\nThe Gemini API quota has been exceeded. Please try again later.\\n\\nGet a free API key: https://aistudio.google.com/app/apikey"
            logger.error(f"Gemini suggestion error: {e}")
            return None
