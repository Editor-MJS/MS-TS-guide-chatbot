import pypdf
import os
import json

def load_pdf_text(pdf_path):
    """
    Loads text from a PDF file.
    """
    if not os.path.exists(pdf_path):
        return None
    
    text_content = ""
    try:
        reader = pypdf.PdfReader(pdf_path)
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
    except Exception as e:
        return f"Error reading PDF: {str(e)}"
        
    return text_content

def load_json_index(json_path):
    """
    Loads and formats the JSON index for the LLM context.
    """
    if not os.path.exists(json_path):
        return None
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert JSON to a readable string format for the LLM
        context = ""
        for item in data:
            context += f"ID: {item.get('ID')}\n"
            context += f"Type: {item.get('장비구분')}\n"
            context += f"Task: {item.get('작업내용')}\n"
            context += f"Situation: {item.get('참고상황')}\n"
            context += f"Objective: {item.get('상세목적')}\n\n"
        return context
    except Exception as e:
        return f"Error reading JSON: {str(e)}"

def get_index_context():
    """
    Prioritizes JSON index from Chatbot_Index_Output, falls back to PDF.
    """
    # Check both current folder and parent folder for the output directory
    possible_paths = [
        os.path.join("Chatbot_Index_Output", "Chatbot_Knowledge_Base.json"),
        os.path.join("..", "Chatbot_Index_Output", "Chatbot_Knowledge_Base.json")
    ]
    
    json_path = None
    for p in possible_paths:
        if os.path.exists(p):
            json_path = p
            break

    pdf_filename = "HPLC_001-030_문서요약_인덱스.pdf"
    pdf_path_fallback = os.path.join("..", pdf_filename)
    
    # 1. Try JSON First (Best structure)
    if json_path:
        return load_json_index(json_path)
    
    # 2. Try PDF fallback
    if os.path.exists(pdf_filename):
        return load_pdf_text(pdf_filename)
    elif os.path.exists(pdf_path_fallback):
        return load_pdf_text(pdf_path_fallback)
        
    return "Index data not found. Please ensure JSON or PDF is present."
