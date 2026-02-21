import streamlit as st
import google.generativeai as genai
import os
import re
import pandas as pd
from dotenv import load_dotenv
from utils import get_index_context

# 0. 초기 설정
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("API Key가 없습니다. .env 파일이나 클라우드 설정을 확인하세요.")
    st.stop()
genai.configure(api_key=api_key)

# 1. 엑셀에서 문서 링크 불러오기
def load_document_links():
    links = {}
    try:
        excel_path = 'document_links.xlsx'
        if not os.path.exists(excel_path):
            excel_path = os.path.join(os.path.dirname(__file__), '..', 'document_links.xlsx')
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            for _, row in df.iterrows():
                inst = str(row['equipment']).upper().strip()
                raw_num = str(row['sheet_no']).strip()
                if '.' in raw_num: raw_num = raw_num.split('.')[0]
                num = raw_num.zfill(3)
                lang = str(row['language']).upper().strip()
                url = str(row['link']).strip()
                if url and url != 'nan':
                    links[(inst, num, lang)] = url
    except Exception: pass
    return links

DOCUMENT_LINKS = load_document_links()

# 2. AI 응답 로직 (모델명: gemini-1.5-flash)
def get_gemini_response(user_prompt):
    full_prompt = f"""
    당신은 품질 관리(QC) 분석기기 문서 안내 봇입니다.
    아래 [INDEX DATA]를 참고하여 사용자가 찾는 문서의 번호(Sheet No), 제목(Title), 장비(Instrument)를 안내하세요.
    - 답변 형식: [장비명]-[번호3자리] (예: HPLC-029)
    - 해결 방법은 설명하지 마세요.
    - 한국어 질문에는 한국어로 답변하세요.

    [INDEX DATA]
    {st.session_state.index_context}

    [User Question]
    {user_prompt}
    """
    model = genai.GenerativeModel("gemini-2.5-flash") # 어제 정상 작동했던 원래 모델명
    response = model.generate_content(full_prompt)
    text = response.text
    
    # 링크 버튼 생성
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', text)
    link_md = ""
    unique_links = set()
    for inst, num in matches:
        key = (inst.upper(), num, lang)
        if key in DOCUMENT_LINKS:
            url = DOCUMENT_LINKS[key]
            if url not in unique_links:
                label = f"{inst}-{num} 문서 바로가기" if lang == "KR" else f"Direct Link: {inst}-{num}"
                link_md += f"\n\n🔗 [{label}]({url})"
                unique_links.add(url)
    
    footer = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 폴더 가기**](https://works.do/FYhb6GY)" if lang=="KR" else "\n\n---\n💡 [**Entire Folder**](https://works.do/FYhb6GY)"
    return text + link_md + footer

# 3. 프리미엄 디자인 UI
st.set_page_config(page_title="MS·TS Guide Chatbot", page_icon="🐻", layout="centered")

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
    [data-testid="stChatMessage"]:nth-child(even) [data-testid="stChatMessageContent"] {
        background-color: #f1f3f5 !important; border-radius: 18px 18px 18px 2px !important;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) { flex-direction: row-reverse !important; }
    div[data-testid="stChatMessage"]:nth-child(odd) [data-testid="stChatMessageContent"] { 
        background: linear-gradient(135deg, #667eea, #764ba2) !important; color: white !important;
        border-radius: 18px 18px 2px 18px !important; text-align: left !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-container">
    <div style="font-size: 2.2rem; font-weight: 700;">MS·TS guide chatbot</div>
    <div style="opacity: 0.9;">문제 증상을 입력하면 지침서 번호를 알려드립니다.</div>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "index_context" not in st.session_state:
    with st.spinner("지식 로딩 중..."):
        st.session_state.index_context = get_index_context()

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# 어제의 예시 질문 버튼 복구
if not st.session_state.messages:
    st.markdown("<div style='color: #888; font-size: 0.9rem; margin-bottom: 10px;'>💡 자주 묻는 질문</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    def click_starter(q):
        st.session_state.messages.append({"role": "user", "content": q})
        with st.chat_message("assistant", avatar="🐻"):
            res = get_gemini_response(q)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
        st.rerun()
    if c1.button("HPLC 피크 갈라짐 해결방법", use_container_width=True): click_starter("HPLC 피크 갈라짐 해결방법 알려줘")
    if c2.button("HPLC 결과 재현성 문제", use_container_width=True): click_starter("HPLC 결과 재현성이 안 좋아")

if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt)
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
