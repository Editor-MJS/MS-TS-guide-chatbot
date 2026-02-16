import pypdf
import os

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

def get_index_context():
    """
    Reads the specific index PDF and returns its content as a string context.
    """
    # Assuming the file is in the same directory or a known path
    # Using the filename provided by the user
    pdf_filename = "HPLC_001-030_문서요약_인덱스.pdf"
    
    # Try looking in current directory
    if os.path.exists(pdf_filename):
        return load_pdf_text(pdf_filename)
        
    return "Index PDF not found. Please ensure 'HPLC_001-030_문서요약_인덱스.pdf' is in the project directory."
