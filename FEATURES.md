# FlowGen AI - Enhanced Features

## Multi-Mode Code Input System

FlowGen AI now supports **three different input modes** for maximum flexibility:

### 1. Code Snippet Mode 📝
- **Use Case**: Quick analysis of small code snippets
- **How to Use**: 
  - Select "Code Snippet" from the dropdown
  - Paste your code directly into the Monaco editor
  - Click "Generate" to create visualizations
- **Best For**: Testing algorithms, learning, quick demos

### 2. Upload File(s) Mode 📄
- **Use Case**: Analyze single or multiple code files
- **How to Use**:
  - Select "Upload File(s)" from the dropdown
  - Click "Choose Files" and select one or more code files
  - Supported formats: `.py`, `.js`, `.java`, `.c`, `.cpp`, `.cc`, `.h`, `.hpp`
  - Click "Generate" to process all files together
- **Best For**: Analyzing related code files, comparing multiple implementations

### 3. Upload Folder Mode 📁
- **Use Case**: Analyze entire project folders
- **How to Use**:
  - Zip your project folder first
  - Select "Upload Folder (as ZIP)" from the dropdown
  - Upload the ZIP file
  - The system will automatically extract and analyze all code files
- **Best For**: Full project analysis, understanding codebase architecture

## Features

### Combined Analysis
When uploading multiple files or folders, FlowGen AI:
- ✅ Detects language for each file automatically
- ✅ Parses all code files (Python, JavaScript, Java, C, C++)
- ✅ Merges function calls, classes, and control flow across files
- ✅ Generates unified flowcharts and workflows
- ✅ Shows which files were processed and their details

### Visual Feedback
- See the list of uploaded files before processing
- Get confirmation of processed files with language detection
- View file sizes and counts
- Color-coded success indicators

## API Endpoints

### New: `/api/analyze-multiple`
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Parameters**: 
  - `files`: Array of UploadFile objects
- **Supports**:
  - Multiple individual files
  - ZIP archives (automatically extracted)
- **Returns**:
  ```json
  {
    "processed_files": [
      {
        "filename": "main.py",
        "language": "python",
        "size": 1234
      }
    ],
    "total_files": 5,
    "flowchart": { ... },
    "workflow": { ... },
    "summaries": { ... }
  }
  ```

### Existing: `/api/analyze`
- Still supports single code snippet analysis
- JSON body with `filename` and `content` fields

## Technical Implementation

### Backend (FastAPI)
- New route handler for multiple file uploads
- ZIP file extraction and processing
- File type filtering (only code files)
- Merged parsed data from multiple sources
- Error handling for invalid files

### Frontend (React)
- Dynamic UI based on input mode
- File selection with multi-file support
- Visual feedback for selected files
- Processed file information display
- Maintained backward compatibility with snippet mode

## Example Use Cases

1. **Learning**: Paste a quick algorithm snippet to see its flow
2. **Code Review**: Upload related files to see how they interact
3. **Project Analysis**: ZIP your entire project to visualize the architecture
4. **Cross-file Dependencies**: See how functions call each other across modules
5. **Refactoring**: Understand code structure before making changes

## Future Enhancements (Potential)
- Drag-and-drop folder upload (without zipping)
- Git repository URL input
- Interactive file tree view
- Per-file individual visualizations
- Export combined diagrams
