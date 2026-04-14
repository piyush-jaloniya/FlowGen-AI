import spacy
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from .services.nlp_service import NLPService
from .services.parser_service import ParserService
from .services.flowchart_service import FlowchartService
from .services.workflow_service import WorkflowService
from .services.llm_service import LLMService
from typing import List, Dict
import zipfile
import io
import os

# Configure logging
logger = logging.getLogger(__name__)

# Security: Input validation limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file (increased for project folders)
MAX_CODE_LENGTH = 500000  # 500k characters (increased for larger files)
MAX_ZIP_SIZE = 200 * 1024 * 1024  # 200MB for ZIP files (increased for projects)
MAX_FILES_IN_ZIP = 500  # Maximum files to process from ZIP (increased)

router = APIRouter()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# -------------------------------------------------------------------
# Initialize core services
# -------------------------------------------------------------------
nlp_core = NLPService()
llm = LLMService()  # Initialize LLM service
parser = ParserService()
flowchart = FlowchartService(parser, nlp_core.nlp)
workflow = WorkflowService(parser, nlp_core.nlp)

# -------------------------------------------------------------------
# Route: /api/analyze
# -------------------------------------------------------------------
@router.post("/analyze")
@limiter.limit("20/minute")
async def analyze_code(
    request: Request,
    file: UploadFile = None,
    code: str = Form(None),
    filename: str = Form(None)
):
    """
    Analyze code and generate both flowchart and workflow visualizations.
    
    **Accepts:**
    - JSON body (from React frontend):
      ```json
      {
        "filename": "example.py",
        "content": "def add(a,b): return a+b"
      }
      ```
    - Multipart/form-data (from Swagger UI) with 'file' or 'code' fields
    
    **Returns:**
    ```json
    {
      "language": "python",
      "flowchart": {"mermaid": "flowchart TD..."},
      "workflow": {"mermaid": "flowchart LR..."},
      "summaries": {...},
      "ai_insights": {"description": "...", "pattern": "...", "suggestions": "..."}
    }
    ```
    
    **Rate Limit:** 20 requests per minute per IP
    
    **Error Codes:**
    - 400: Empty code input
    - 413: Code content too large (max 100k characters)
    - 429: Rate limit exceeded
    - 500: Server error
    """
    try:
        # --- Detect request type ---
        if request.headers.get("content-type", "").startswith("application/json"):
            # Frontend JSON request
            data = await request.json()
            filename = data.get("filename", "input.txt")
            content = data.get("content", "")
        else:
            # Swagger multipart form-data
            if file:
                content = (await file.read()).decode("utf-8")
                filename = file.filename
            else:
                content = code or ""
                filename = filename or "input.txt"

        if not content.strip():
            raise HTTPException(status_code=400, detail="Empty code input received.")
        
        # Security: Validate content length
        if len(content) > MAX_CODE_LENGTH:
            raise HTTPException(
                status_code=413, 
                detail=f"Code content too large. Maximum {MAX_CODE_LENGTH} characters allowed."
            )


        # --- Run parsing & visualization ---
        lang = parser.detect_language(filename, content)
        parsed_data = parser.parse_code(lang, filename, content)

        flowchart_data = flowchart.build(parsed_data)
        workflow_data = workflow.build(parsed_data)

        # ✅ Generate NLP summaries (function descriptions)
        summaries = nlp_core.summarize_code(parsed_data)

        # ✅ NEW: LLM-powered analysis (if enabled)
        llm_analysis = {}
        if llm.is_enabled():
            logger.info("LLM is enabled, analyzing code...")
            # Get code description
            description = llm.analyze_code_snippet(content, lang)
            logger.debug(f"Description: {description}")
            if description:
                llm_analysis["description"] = description
            
            # Detect algorithm pattern
            pattern = llm.detect_algorithm_pattern(content, lang)
            logger.debug(f"Pattern: {pattern}")
            if pattern:
                llm_analysis["pattern"] = pattern
            
            # Get improvement suggestions
            suggestions = llm.suggest_improvements(content, lang)
            logger.debug(f"Suggestions: {suggestions}")
            if suggestions:
                llm_analysis["suggestions"] = suggestions
            
            logger.debug(f"Final LLM analysis: {llm_analysis}")
        else:
            logger.info("LLM is not enabled")

        # --- Return combined response ---
        response_data = {
            "language": lang,
            "flowchart": flowchart_data,
            "workflow": workflow_data,
            "summaries": summaries
        }
        
        # Add LLM analysis if available
        if llm_analysis:
            response_data["ai_insights"] = llm_analysis

        return JSONResponse(response_data)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("Backend error:", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# -------------------------------------------------------------------
# Optional extra routes (for direct visualization endpoints)
# -------------------------------------------------------------------

@router.post("/flowchart")
@limiter.limit("20/minute")
async def flowchart_only(request: Request):
    """Generate only flowchart JSON from code"""
    try:
        data = await request.json()
        filename = data.get("filename", "input.txt")
        content = data.get("content", "")
        lang = parser.detect_language(filename, content)
        parsed = parser.parse_code(lang, filename, content)
        flow_data = flowchart.build(parsed)
        return JSONResponse({"language": lang, "flowchart": flow_data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------------------
# Route: /api/analyze-multiple (for file/folder upload)
# -------------------------------------------------------------------
@router.post("/analyze-multiple")
@limiter.limit("10/minute")  # Lower limit for expensive multi-file operations
async def analyze_multiple_files(
    request: Request,
    files: List[UploadFile] = File(...)
):
    """
    Accepts multiple files or a zipped folder.
    Analyzes all code files and returns combined visualization.
    """
    try:
        all_parsed_data = []
        processed_files = []

        for file in files:
            filename = file.filename
            content_bytes = await file.read()
            
            # Security: Validate file size
            if len(content_bytes) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{filename}' is too large. Maximum {MAX_FILE_SIZE // (1024*1024)}MB allowed."
                )
            
            # Handle ZIP files (folder upload)
            if filename.endswith('.zip'):
                # Security: Validate ZIP size
                if len(content_bytes) > MAX_ZIP_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"ZIP file too large. Maximum {MAX_ZIP_SIZE // (1024*1024)}MB allowed."
                    )
                
                with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                    file_count = 0
                    for zip_info in z.namelist():
                        # Skip directories and non-code files
                        if zip_info.endswith('/') or zip_info.startswith('__MACOSX'):
                            continue
                        
                        # Security: Limit number of files to prevent ZIP bomb
                        file_count += 1
                        if file_count > MAX_FILES_IN_ZIP:
                            raise HTTPException(
                                status_code=413,
                                detail=f"Too many files in ZIP. Maximum {MAX_FILES_IN_ZIP} files allowed."
                            )
                        
                        # Filter for code files
                        ext = os.path.splitext(zip_info)[1].lower()
                        if ext in ['.py', '.js', '.java', '.c', '.cpp', '.cc', '.h', '.hpp']:
                            file_content = z.read(zip_info).decode('utf-8', errors='ignore')
                            
                            # Security: Validate individual file content length
                            if len(file_content) > MAX_CODE_LENGTH:
                                continue  # Skip files that are too large
                            
                            if file_content.strip():
                                lang = parser.detect_language(zip_info, file_content)
                                parsed = parser.parse_code(lang, zip_info, file_content)
                                all_parsed_data.append(parsed)
                                processed_files.append({
                                    "filename": zip_info,
                                    "language": lang,
                                    "size": len(file_content)
                                })
            else:
                # Handle individual code files
                content = content_bytes.decode('utf-8', errors='ignore')
                
                # Security: Validate content length
                if len(content) > MAX_CODE_LENGTH:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File content too large. Maximum {MAX_CODE_LENGTH} characters allowed."
                    )
                
                if content.strip():
                    lang = parser.detect_language(filename, content)
                    # Only process code files
                    if lang != "text":
                        parsed = parser.parse_code(lang, filename, content)
                        all_parsed_data.append(parsed)
                        processed_files.append({
                            "filename": filename,
                            "language": lang,
                            "size": len(content)
                        })

        if not all_parsed_data:
            raise HTTPException(status_code=400, detail="No valid code files found.")

        # Merge all parsed data
        merged_data = _merge_parsed_data(all_parsed_data)
        
        # Generate visualizations
        flowchart_data = flowchart.build(merged_data)
        workflow_data = workflow.build(merged_data)
        summaries = nlp_core.summarize_code(merged_data)

        # ✅ LLM analysis for multi-file projects (if enabled)
        llm_analysis = {}
        if llm.is_enabled() and processed_files:
            # Analyze first substantial code file for insights
            substantial_file = None
            substantial_content = None
            
            # Find first file with actual code content
            for file in files:
                filename = file.filename
                if filename.endswith('.zip'):
                    # For ZIP files, we need to re-read to get content
                    # This is inefficient but necessary for LLM analysis
                    await file.seek(0)  # Reset file pointer
                    content_bytes = await file.read()
                    with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                        for zip_info in z.namelist():
                            if zip_info.endswith('/') or zip_info.startswith('__MACOSX'):
                                continue
                            ext = os.path.splitext(zip_info)[1].lower()
                            if ext in ['.py', '.js', '.java', '.c', '.cpp', '.cc', '.h', '.hpp']:
                                file_content = z.read(zip_info).decode('utf-8', errors='ignore')
                                if file_content.strip() and len(file_content) <= MAX_CODE_LENGTH:
                                    substantial_content = file_content
                                    substantial_file = zip_info
                                    break
                        if substantial_content:
                            break
                else:
                    # For individual files, read content
                    await file.seek(0)
                    content_bytes = await file.read()
                    content = content_bytes.decode('utf-8', errors='ignore')
                    if content.strip() and len(content) <= MAX_CODE_LENGTH:
                        substantial_content = content
                        substantial_file = filename
                        break
            
            if substantial_content and substantial_file:
                # Find language for this file
                file_lang = "python"  # default
                for pf in processed_files:
                    if pf['filename'] == substantial_file:
                        file_lang = pf['language']
                        break
                
                # Collect project info
                file_count = len(processed_files)
                languages = list(set([f['language'] for f in processed_files]))
                total_size = sum([f['size'] for f in processed_files])
                project_info = f"Project with {file_count} file(s), {total_size} total characters, using {', '.join(languages)}"
                
                # Analyze with actual code content
                description = llm.analyze_code_snippet(
                    f"Project overview: {project_info}\nAnalyzing main file: {substantial_file}\n\n{substantial_content[:5000]}", 
                    file_lang
                )
                if description:
                    llm_analysis["description"] = description
                
                pattern = llm.detect_algorithm_pattern(substantial_content, file_lang)
                if pattern and pattern != "Unknown":
                    llm_analysis["pattern"] = pattern
                
                suggestions = llm.suggest_improvements(substantial_content, file_lang)
                if suggestions:
                    llm_analysis["suggestions"] = suggestions
            
            # Add project summary
            llm_analysis["project_summary"] = f"Successfully analyzed {len(processed_files)} file(s) in {', '.join(set([f['language'] for f in processed_files]))}"

        response_data = {
            "processed_files": processed_files,
            "total_files": len(processed_files),
            "flowchart": flowchart_data,
            "workflow": workflow_data,
            "summaries": summaries
        }
        
        if llm_analysis:
            response_data["ai_insights"] = llm_analysis

        return JSONResponse(response_data)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error("Backend error:", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# -------------------------------------------------------------------
# Cache Management Endpoint
# -------------------------------------------------------------------
@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics for monitoring performance.
    
    **Returns:**
    ```json
    {
      "parse_cache": {
        "size": 45,
        "maxsize": 1000,
        "hits": 120,
        "misses": 45
      },
      "diagram_cache": {
        "size": 30,
        "maxsize": 500,
        "hits": 85,
        "misses": 30
      }
    }
    ```
    """
    from app.services.cache_service import cache_service
    return cache_service.get_cache_stats()


@router.post("/cache/clear")
async def clear_cache():
    """
    Clear all caches (admin operation).
    
    **Returns:**
    ```json
    {
      "message": "All caches cleared successfully"
    }
    ```
    """
    from app.services.cache_service import cache_service
    cache_service.clear_cache()
    return {"message": "All caches cleared successfully"}



def _merge_parsed_data(parsed_list: List[Dict]) -> Dict:
    """
    Intelligently merge multiple parsed data dictionaries.
    Uses ProjectAnalyzer for smart filtering and prioritization.
    """
    # TEMPORARILY DISABLED FOR TESTING
    # from .services.project_analyzer import ProjectAnalyzer
    
    # # Use smart merging for large projects
    # if len(parsed_list) > 5:  # More than 5 files
    #     try:
            # analyzer = ProjectAnalyzer(max_functions=50)
            # merged = analyzer.smart_merge(parsed_list, max_nodes=50)
            # logger.info(f"Smart merge: {merged.get('metadata', {})}")
            # return merged
    #     except Exception as e:
    #         logger.error(f"Smart merge failed: {e}", exc_info=True)
    #         logger.info("Falling back to simple merge")
    #         # Fall through to simple merge
    
    # Simple merge for all projects (testing)
    logger.info(f"Using simple merge for {len(parsed_list)} files")
    merged = {
        "functions": [],
        "classes": [],
        "imports": [],
        "calls": [],
        "control_flow": []
    }
    
    for parsed in parsed_list:
        merged["functions"].extend(parsed.get("functions", []))
        merged["classes"].extend(parsed.get("classes", []))
        merged["imports"].extend(parsed.get("imports", []))
        merged["calls"].extend(parsed.get("calls", []))
        merged["control_flow"].extend(parsed.get("control_flow", []))
    
    logger.info(f"Simple merge result: {len(merged['functions'])} functions")
    return merged


@router.post("/workflow")
@limiter.limit("20/minute")
async def workflow_only(request: Request):
    """Generate only workflow JSON from code"""
    try:
        data = await request.json()
        filename = data.get("filename", "input.txt")
        content = data.get("content", "")
        lang = parser.detect_language(filename, content)
        parsed = parser.parse_code(lang, filename, content)
        workflow_data = workflow.build(parsed)
        return JSONResponse({"language": lang, "workflow": workflow_data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
