import streamlit as st
import google.generativeai as genai
import os
import csv
import re
from dotenv import load_dotenv
from utils import get_index_context

# Load environment variables
load_dotenv()

# Configure Gemini API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Google API Key not found. Please set it in .env file.")
    st.stop()

genai.configure(api_key=api_key)

# Generation Config (어제의 안정적인 설정)
generation_config = {
  "temperature": 0.0,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

# 로컬 CSV에서 링크 로드 (어제 방식)
def load_document_links():
    links = {}
    csv_path = 'document_links.csv'
    try:
        if os.path.exists(csv_path):
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Key: (EQUIPMENT, SHEET_NO, LANGUAGE)
                    key = (row['equipment'].upper(), row['sheet_no'], row['language'].upper())
                    if row['link'] and row['link'].strip():
                        links[key] = row['link'].strip()
    except Exception: pass
    return links

DOCUMENT_LINKS = load_document_links()

# 어제의 똑똑한 시스템 지침 (PDF 베이스)
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침 (어제 완성 버전)

1. 언어 규칙: 한글 포함 시 한국어 답변, 영어만 있으면 영어 답변.
2. 역할: 업로드된 인덱스 PDF만 근거로 문서 위치(Sheet No / Title / Instrument) 안내.
3. 해결 방법은 절대 대답하지 말 것. 오직 위치만 안내.
4. 출력 형식: [장비명]-[번호3자리] (예: HPLC-029)
"""

def get_gemini_response(user_prompt):
    full_prompt = f"""
    [SYSTEM INSTRUCTION]
    {SYSTEM_PROMPT}
    [INDEX DATA (PDF Contents)]
    {st.session_state.get('index_context', '인덱스를 불러올 수 없습니다.')}
    [USER QUESTION]
    {user_prompt}
    """
    # 어제 완벽했던 그 모델 이름
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(full_prompt, generation_config=generation_config)
    text = response.text
    
    # 링크 매칭
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', text)
    link_md = ""
    for inst, num in matches:
        key = (inst.upper(), num, lang)
        if key in DOCUMENT_LINKS:
            url = DOCUMENT_LINKS[key]
            label = f"{inst}-{num} 문서 바로가기" if lang == "KR" else f"Direct Link: {inst}-{num}"
            link_md += f"\n\n🔗 [{label}]({url})"
            
    footer = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 폴더 가기**](https://works.do/FYhb6GY)"
    return text + link_md + footer

# UI 디자인 (어제 버전)
st.set_page_config(page_title="MS·TS Guide Chatbot", page_icon="🐻", layout="centered")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    header {visibility: hidden;}
    .header-container {
        background: linear-gradient(135deg, #3B28CC 0%, #E062E6 100%);
        padding: 3rem 2rem; border-radius: 0 0 25px 25px; color: white; margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-container"><div style="font-size: 2.2rem; font-weight: 700;">MS·TS guide chatbot</div></div>', unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "index_context" not in st.session_state:
    st.session_state.index_context = get_index_context()

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# 어제의 예시 버튼
if not st.session_state.messages:
    st.markdown("<div style='color:#888;'>💡 자주 묻는 질문</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    def click_starter(q):
        st.session_state.messages.append({"role": "user", "content": q})
        with st.chat_message("assistant", avatar="🐻"):
            res = get_gemini_response(q)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
        st.rerun()
    if c1.button("HPLC 피크 갈라짐 해결", use_container_width=True): click_starter("HPLC 피크 갈라짐 해결방법 알려줘")
    if c2.button("HPLC 결과 재현성 문제", use_container_width=True): click_starter("HPLC 결과 재현성이 안 좋아")

if prompt := st.chat_input("증상을 입력하세요..."):
    with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
