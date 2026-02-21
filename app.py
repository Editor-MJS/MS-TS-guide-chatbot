import streamlit as st
import google.generativeai as genai
import os
import csv
import re
from dotenv import load_dotenv
from utils import get_index_context

# 0. 초기 설정
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Google API Key not found. Please set it in .env file.")
    st.stop()

genai.configure(api_key=api_key)

# 1. 문서 링크 로드 (어제 고정 버전)
def load_document_links():
    links = {}
    csv_path = 'document_links.csv'
    try:
        if os.path.exists(csv_path):
            with open(csv_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row['equipment'].upper(), row['sheet_no'], row['language'].upper())
                    if row['link'] and row['link'].strip():
                        links[key] = row['link'].strip()
    except Exception: pass
    return links

DOCUMENT_LINKS = load_document_links()

# 2. 어제의 가장 똑똑했던 시스템 지침 복구 (9가지 규칙 버전)
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침 (어제 완벽 버전)

1. 언어 규칙: 한글이 한 글자라도 있으면 한국어로, 영어만 있으면 영어로 답변. 단, Title과 Sheet No는 원문 그대로 출력.
2. 역할: 업로드된 인덱스 PDF만 근거로 Sheet No / Title / Instrument만 안내. 해결 방법 등은 절대 출력 금지.
3. 매칭: 검색1(증상 그대로), 검색2(카테고리명), 검색3(확장 키워드) 순서로 꼼꼼히 검색.
4. 시트번호 인식/정규화: 반드시 [장비명]-[###] 형식으로 패딩하여 표기 (예: HPLC-029).
5. 랭킹: 관련성 높은 순서대로 최대 3개 출력.
6. 전체 문서함 안내: 사용자가 요청할 때만 링크 안내 (https://works.do/FYhb6GY).
"""

def get_gemini_response(user_prompt):
    full_prompt = f"""
    [SYSTEM INSTRUCTION]
    {SYSTEM_PROMPT}

    [INDEX DATA (PDF SOURCE)]
    {st.session_state.get('index_context', '')}

    [USER QUESTION]
    {user_prompt}
    """
    # 어제의 그 모델!
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(full_prompt)
    text = response.text
    
    # 링크 버튼 로직
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', text)
    link_md = ""
    unique_links = set()
    for inst, num in matches:
        key = (inst.upper(), num, lang)
        if key in DOCUMENT_LINKS:
            url = DOCUMENT_LINKS[key]
            if url not in unique_links:
                label = f"{inst}-{num} 문서 바로가기" if lang == "KR" else f"View Document {inst}-{num}"
                link_md += f"\n\n🔗 [{label}]({url})"
                unique_links.add(url)
    
    footer = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함(폴더)**](https://works.do/FYhb6GY)에서 직접 확인하실 수 있습니다."
    return text + link_md + footer

# 3. 어제의 프리미엄 UI 디자인 복구
st.set_page_config(page_title="MS·TS guide chatbot", page_icon="🐻", layout="centered")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    header {visibility: hidden;}
    .header-container {
        background: linear-gradient(135deg, #3B28CC 0%, #E062E6 100%);
        padding: 3rem 2rem; border-radius: 0 0 25px 25px; color: white; margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .stButton>button { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-container">
    <div style="font-size: 2.2rem; font-weight: 700;">MS·TS guide chatbot</div>
    <div style="opacity: 0.9;">문제 증상을 입력하면 지침서 번호를 안내해 드립니다.</div>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "index_context" not in st.session_state:
    with st.spinner("지식 베이스를 읽어오는 중입니다..."):
        st.session_state.index_context = get_index_context()

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# 어제의 대화 스타터 (100% 동일한 문구)
if not st.session_state.messages:
    st.markdown("<div style='color: #888; font-size: 0.9rem; margin-bottom: 10px;'>💡 테스트 질문</div>", unsafe_allow_html=True)
    if st.button("HPLC 피크 갈라짐 해결방법 알려줘", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "HPLC 피크 갈라짐 해결방법 알려줘"})
        with st.chat_message("assistant", avatar="🐻"):
            res = get_gemini_response("HPLC 피크 갈라짐 해결방법 알려줘")
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
        st.rerun()

if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt)
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
