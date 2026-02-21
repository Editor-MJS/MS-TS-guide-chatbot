import pypdf
import os

def load_pdf_text(pdf_path):
    """PDF에서 텍스트를 추출하는 어제 버전"""
    if not os.path.exists(pdf_path):
        return "PDF 파일을 찾을 수 없습니다."
    
    text_content = ""
    try:
        reader = pypdf.PdfReader(pdf_path)
        for page in reader.pages:
            text_content += page.extract_text() + "\n"
    except Exception as e:
        return f"PDF 읽기 오류: {str(e)}"
    return text_content

def get_index_context():
    """어제의 단순 PDF 로드 방식"""
    pdf_filename = "HPLC_001-030_문서요약_인덱스.pdf"
    if os.path.exists(pdf_filename):
        return load_pdf_text(pdf_filename)
    return "인덱스 PDF 파일이 없습니다."
