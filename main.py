import os
import json
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from services import TextProcessor, TextFilterService
import uvicorn
from typing import List, Dict, Any

app = FastAPI()

# Ensure templates directory exists
os.makedirs("templates", exist_ok=True)

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/process-text")
async def process_text(request: Request):
    data = await request.json()
    text = data.get("text", "")
    max_chars = data.get("max_chars", 1500)
    min_chars = data.get("min_chars", 30)
    
    processor = TextProcessor(max_chars=max_chars, min_chars_to_merge=min_chars)
    chunks = processor.process(text)
    return {"chunks": chunks}

@app.post("/api/filter-text")
async def filter_text(request: Request):
    data = await request.json()
    text = data.get("text", "")
    options = data.get("options", {})
    junk_keywords = data.get("junk_keywords", "")
    phonetic_dict = data.get("phonetic_dict", [])
    
    result = TextFilterService.process(text, options, junk_keywords, phonetic_dict)
    return {"result": result}

@app.post("/api/upload-file")
async def upload_file(file: UploadFile = File(...)):
    content = ""
    filename = file.filename.lower()
    
    if filename.endswith(".txt"):
        content = (await file.read()).decode("utf-8")
    elif filename.endswith(".docx"):
        from docx import Document
        import io
        doc_bytes = await file.read()
        doc = Document(io.BytesIO(doc_bytes))
        content = "\n".join([para.text for para in doc.paragraphs])
    else:
        return JSONResponse(status_code=400, content={"error": "Unsupported file format"})
        
    return {"content": content}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
