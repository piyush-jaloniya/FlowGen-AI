"""
Project Analyzer for Multi-File Code Analysis
Provides smart filtering, scoring, and grouping for large projects.
"""
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    """Analyzes multi-file projects and provides smart filtering."""
    
    def __init__(self, max_functions: int = 50):
        self.max_functions = max_functions
    
    def score_function(self, func: Dict[str, Any]) -> int:
        """
        Score a function based on importance.
        Higher scores = more important to include in diagram.
        """
        score = 0
        name = func.get('name', '')
        
        # Main function gets highest priority
        if name == 'main':
            score += 100
        
        # Public functions (no underscore prefix) are more important
        if not name.startswith('_'):
            score += 50
        
        # Functions with many calls are central to the codebase
        calls = func.get('calls', [])
        score += len(calls) * 5
        
        # Functions with control flow are more complex/important
        body = func.get('body', [])
        score += len(body) * 2
        
        # Longer functions are generally more important
        lines = func.get('lines', 0)
        score += min(lines, 50)  # Cap at 50 to avoid bias
        
        # Functions that are called by others are important
        # (This would require cross-reference analysis, skipping for now)
        
        return score
    
    def is_trivial(self, func: Dict[str, Any]) -> bool:
        """
        Determine if a function is trivial and should be filtered out.
        """
        name = func.get('name', '')
        
        # Test functions
        if name.startswith('test_'):
            return True
        
        # Setup/teardown functions
        if name in ['setUp', 'tearDown', 'setUpClass', 'tearDownClass']:
            return True
        
        # Property getters/setters
        if name.startswith('get_') or name.startswith('set_'):
            body = func.get('body', [])
            if len(body) <= 1:  # Simple getter/setter
                return True
        
        # Very short functions with no logic
        lines = func.get('lines', 0)
        calls = func.get('calls', [])
        body = func.get('body', [])
        
        if lines < 3 and not calls and not body:
            return True
        
        return False
    
    def smart_merge(self, parsed_list: List[Dict], max_nodes: int = None) -> Dict[str, Any]:
        """
        Intelligently merge multiple parsed files.
        Filters and prioritizes functions based on importance.
        
        Args:
            parsed_list: List of parsed file data
            max_nodes: Maximum number of functions to include
            
        Returns:
            Merged parsed data with top functions
        """
        if max_nodes is None:
            max_nodes = self.max_functions
        
        # Collect all functions with metadata
        all_functions = []
        for parsed in parsed_list:
            filename = parsed.get('filename', 'unknown')
            for func in parsed.get('functions', []):
                # Skip if function data is invalid
                if not isinstance(func, dict) or not func.get('name'):
                    continue
                
                # Add source file info
                func['source_file'] = filename
                
                # Skip trivial functions
                if self.is_trivial(func):
                    logger.debug(f"Skipping trivial function: {func.get('name')} from {filename}")
                    continue
                
                # Clean up function data - ensure all fields are safe
                func['name'] = str(func.get('name', 'unknown'))
                func['args'] = func.get('args', [])
                func['body'] = func.get('body', [])
                func['calls'] = func.get('calls', [])
                func['lines'] = func.get('lines', 0)
                
                # Calculate importance score
                func['importance_score'] = self.score_function(func)
                all_functions.append(func)
        
        logger.info(f"Collected {len(all_functions)} non-trivial functions from {len(parsed_list)} files")
        
        # Sort by importance score
        all_functions.sort(key=lambda f: f['importance_score'], reverse=True)
        
        # Take top N functions
        selected_functions = all_functions[:max_nodes]
        
        logger.info(f"Selected top {len(selected_functions)} functions for visualization")
        
        # Log which functions were selected
        if selected_functions:
            top_5 = selected_functions[:5]
            logger.debug("Top 5 functions:")
            for func in top_5:
                logger.debug(f"  - {func.get('name')} (score: {func.get('importance_score')}) from {func.get('source_file')}")
        
        # Extract calls from selected functions
        all_calls = []
        for func in selected_functions:
            calls = func.get('calls', [])
            all_calls.extend(calls)
        
        # Build merged data
        merged = {
            'functions': selected_functions,
            'classes': [],  # Simplified - could be enhanced later
            'imports': [],  # Not needed for visualization
            'calls': all_calls,
            'control_flow': [],
            'metadata': {
                'total_files': len(parsed_list),
                'total_functions': len(all_functions),
                'selected_functions': len(selected_functions),
                'filtered_out': len(all_functions) - len(selected_functions)
            }
        }
        
        return merged
    
    def group_by_module(self, parsed_list: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Group parsed data by module/directory.
        
        Args:
            parsed_list: List of parsed file data
            
        Returns:
            Dictionary mapping module names to parsed data
        """
        groups = {}
        
        for parsed in parsed_list:
            filename = parsed.get('filename', 'unknown')
            
            # Extract module name (first directory in path)
            parts = filename.split('/')
            if len(parts) > 1:
                module = parts[0]
            else:
                module = 'root'
            
            if module not in groups:
                groups[module] = []
            
            groups[module].append(parsed)
        
        logger.info(f"Grouped {len(parsed_list)} files into {len(groups)} modules")
        return groups
    
    def get_project_summary(self, parsed_list: List[Dict]) -> str:
        """
        Generate a summary of the project.
        
        Args:
            parsed_list: List of parsed file data
            
        Returns:
            Summary string
        """
        total_files = len(parsed_list)
        
        total_functions = sum(
            len(p.get('functions', [])) 
            for p in parsed_list
        )
        
        languages = set(p.get('language', 'unknown') for p in parsed_list)
        
        return f"{total_files} files, {total_functions} functions ({', '.join(languages)})"
