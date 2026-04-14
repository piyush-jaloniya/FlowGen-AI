import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e)
                    
                    # Don't retry on quota/rate limit errors
                    if any(keyword in error_msg.lower() for keyword in ['429', 'quota', 'resourceexhausted', 'rate limit']):
                        logger.warning(f"Quota/rate limit error, not retrying: {e}")
                        raise
                    
                    # Don't retry on authentication errors
                    if any(keyword in error_msg.lower() for keyword in ['401', 'unauthorized', 'api key']):
                        logger.error(f"Authentication error, not retrying: {e}")
                        raise
                    
                    if attempt < max_retries - 1:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {type(e).__name__}: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}")
                        raise
            return None
        return wrapper
    return decorator


def chunk_code(code: str, max_lines: int = 50) -> list[str]:
    """
    Split code into chunks of maximum lines.
    
    Args:
        code: Source code to chunk
        max_lines: Maximum lines per chunk
        
    Returns:
        List of code chunks
    """
    lines = code.split('\n')
    
    if len(lines) <= max_lines:
        return [code]
    
    chunks = []
    for i in range(0, len(lines), max_lines):
        chunk_lines = lines[i:i + max_lines]
        chunks.append('\n'.join(chunk_lines))
    
    logger.info(f"Split code into {len(chunks)} chunks ({max_lines} lines each)")
    return chunks


def calculate_code_complexity(code: str) -> int:
    """
    Calculate cyclomatic complexity of code.
    
    Args:
        code: Source code
        
    Returns:
        Complexity score
    """
    complexity = 1  # Base complexity
    
    # Keywords that increase complexity
    keywords = [
        'if', 'elif', 'else', 'for', 'while', 
        'and', 'or', 'case', 'catch', 'except',
        '&&', '||', '?'
    ]
    
    code_lower = code.lower()
    for keyword in keywords:
        # Count occurrences with word boundaries
        complexity += code_lower.count(f' {keyword} ')
        complexity += code_lower.count(f' {keyword}(')
        complexity += code_lower.count(f'({keyword} ')
    
    return complexity


def get_code_metrics(code: str, language: str) -> dict:
    """
    Get basic code metrics.
    
    Args:
        code: Source code
        language: Programming language
        
    Returns:
        Dictionary of metrics
    """
    lines = code.split('\n')
    non_empty_lines = [l for l in lines if l.strip()]
    
    # Count different elements based on language
    if language.lower() == 'python':
        functions = len([l for l in lines if l.strip().startswith('def ')])
        classes = len([l for l in lines if l.strip().startswith('class ')])
        imports = len([l for l in lines if l.strip().startswith(('import ', 'from '))])
    elif language.lower() in ['javascript', 'typescript']:
        functions = len([l for l in lines if 'function ' in l or '=>' in l])
        classes = len([l for l in lines if 'class ' in l])
        imports = len([l for l in lines if l.strip().startswith(('import ', 'require('))])
    else:
        functions = 0
        classes = 0
        imports = 0
    
    loops = len([l for l in lines if any(kw in l for kw in ['for ', 'while '])])
    conditions = len([l for l in lines if 'if ' in l])
    
    return {
        'total_lines': len(lines),
        'code_lines': len(non_empty_lines),
        'functions': functions,
        'classes': classes,
        'imports': imports,
        'loops': loops,
        'conditions': conditions,
        'complexity': calculate_code_complexity(code)
    }
