import spacy
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from .services.nlp_service import NLPService
from .services.parser_service import ParserService
from .services.flowchart_service import FlowchartService
from .services.workflow_service import WorkflowService
from .services.llm_service import LLMService
import traceback
from typing import List, Dict
import zipfile
import io
import os

router = APIRouter()

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
async def analyze_code(
    request: Request,
    file: UploadFile = None,
    code: str = Form(None),
    filename: str = Form(None)
):
    """
    Accepts:
    - JSON body (from React frontend)
      {
        "filename": "example.py",
        "content": "def add(a,b): return a+b"
      }
    - or multipart/form-data (from Swagger UI)
      with 'file' or 'code' fields.
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
            print(f"🤖 LLM is enabled, analyzing code...")
            # Get code description
            description = llm.analyze_code_snippet(content, lang)
            print(f"📝 Description: {description}")
            if description:
                llm_analysis["description"] = description
            
            # Detect algorithm pattern
            pattern = llm.detect_algorithm_pattern(content, lang)
            print(f"🎯 Pattern: {pattern}")
            if pattern:
                llm_analysis["pattern"] = pattern
            
            # Get improvement suggestions
            suggestions = llm.suggest_improvements(content, lang)
            print(f"💡 Suggestions: {suggestions}")
            if suggestions:
                llm_analysis["suggestions"] = suggestions
            
            print(f"✅ Final LLM analysis: {llm_analysis}")
        else:
            print("⚠️  LLM is not enabled")

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
        print("\n--- BACKEND ERROR TRACE ---")
        traceback.print_exc()
        print("--- END TRACE ---\n")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


# -------------------------------------------------------------------
# Optional extra routes (for direct visualization endpoints)
# -------------------------------------------------------------------

@router.post("/flowchart")
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
async def analyze_multiple_files(
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
            
            # Handle ZIP files (folder upload)
            if filename.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(content_bytes)) as z:
                    for zip_info in z.namelist():
                        # Skip directories and non-code files
                        if zip_info.endswith('/') or zip_info.startswith('__MACOSX'):
                            continue
                        
                        # Filter for code files
                        ext = os.path.splitext(zip_info)[1].lower()
                        if ext in ['.py', '.js', '.java', '.c', '.cpp', '.cc', '.h', '.hpp']:
                            file_content = z.read(zip_info).decode('utf-8', errors='ignore')
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
            # Collect all code content for analysis
            all_code_content = []
            for file_data in processed_files:
                all_code_content.append(f"# File: {file_data['filename']}\n")
            
            # Create a summary of the project structure
            file_count = len(processed_files)
            languages = list(set([f['language'] for f in processed_files]))
            total_size = sum([f['size'] for f in processed_files])
            
            # Generate detailed project summary
            project_info = f"Project with {file_count} file(s), {total_size} total characters, using {', '.join(languages)}"
            
            # Analyze first substantial code file for insights
            substantial_file = None
            for i, data in enumerate(all_parsed_data):
                if data.get('functions') or data.get('classes'):
                    substantial_file = i
                    break
            
            if substantial_file is not None:
                # Get the content of the first substantial file for LLM analysis
                file_info = processed_files[substantial_file]
                
                # Try to get description and pattern from the main file
                description = llm.analyze_code_snippet(
                    f"Project overview: {project_info}\nAnalyzing main file: {file_info['filename']}", 
                    file_info['language']
                )
                if description:
                    llm_analysis["description"] = description
                
                pattern = llm.detect_algorithm_pattern("", file_info['language'])
                if pattern and pattern != "Unknown":
                    llm_analysis["pattern"] = pattern
                
                suggestions = llm.suggest_improvements("", file_info['language'])
                if suggestions:
                    llm_analysis["suggestions"] = suggestions
            
            # Add project summary
            llm_analysis["project_summary"] = f"✅ Successfully analyzed {file_count} file(s) in {', '.join(languages)}"

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
        print("\n--- BACKEND ERROR TRACE ---")
        traceback.print_exc()
        print("--- END TRACE ---\n")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


def _merge_parsed_data(parsed_list: List[Dict]) -> Dict:
    """Merge multiple parsed data dictionaries into one."""
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
    
    return merged


@router.post("/workflow")
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
