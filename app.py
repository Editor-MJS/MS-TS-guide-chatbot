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
    st.error("Google API Key not found.")
    st.stop()
genai.configure(api_key=api_key)

# 1. 문서 링크 로드
def load_document_links():
    links = {}
    try:
        if os.path.exists('document_links.csv'):
            with open('document_links.csv', mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    key = (row['equipment'].upper(), row['sheet_no'], row['language'].upper())
                    if row['link'] and row['link'].strip():
                        links[key] = row['link'].strip()
    except Exception: pass
    return links

DOCUMENT_LINKS = load_document_links()

# 2. 강화된 시스템 지침 (가독성 및 언어 통일)
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침

1. 언어 규칙 (엄격 준수)
* Input has Korean -> Total Answer in Korean.
* Input is only English -> Total Answer in English (including classification logic).
* No hybrid language. Title and Sheet No remain original.

2. 가독성 규칙 (강제 줄바꿈)
* 1순위, 2순위, 3순위 사이에는 반드시 빈 줄을 추가하여 시각적으로 분리할 것.
* 각 문장은 명확하게 개별 줄을 사용할 것.

3. 출력 템플릿
[분류 근거]
질문 키워드 '__'가 '__' 카테고리로 분류되었습니다. (English if user asked in English)

분류
Doc Type: Troubleshooting
Category:

확인할 문서
1순위: [번호] / [제목] / [장비명]
<빈 줄>
2순위: [번호] / [제목] / [장비명]
<빈 줄>
3순위: [번호] / [제목] / [장비명]

열람 방법
보안 링크에 접속한 후 해당 장비 폴더에서 해당 번호의 PDF를 열람하세요.
"""

def get_gemini_response(user_prompt):
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    
    full_prompt = f"""
    {SYSTEM_PROMPT}
    [INDEX DATA]
    {st.session_state.index_context}
    [USER QUESTION]
    {user_prompt}
    """
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(full_prompt)
    text = response.text
    
    # 가독성 보정: 1, 2, 3순위 앞에 줄바꿈 강제 추가
    formatted_text = text.replace("2순위:", "\n\n2순위:").replace("3순위:", "\n\n3순위:")
    
    # 링크 버튼 로직
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', formatted_text)
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
    
    footer = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함(폴더)**](https://works.do/FYhb6GY)" if lang=="KR" else "\n\n---\n💡 [**Check Entire Folder**](https://works.do/FYhb6GY)"
    return formatted_text + link_md + footer

# 3. UI 디자인
st.set_page_config(page_title="MS·TS guide chatbot", page_icon="🐻", layout="centered")

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

st.markdown("""
<div class="header-container">
    <div style="font-size: 2.2rem; font-weight: 700;">MS·TS guide chatbot</div>
    <div style="opacity: 0.9;">문제 증상을 입력하면 지침서 번호를 알려드립니다.</div>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "index_context" not in st.session_state:
    st.session_state.index_context = get_index_context()

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# 스타터 버튼
if not st.session_state.messages:
    st.markdown("<div style='color: #888; font-size: 0.9rem; margin-bottom: 10px;'>💡 테스트 질문</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    def click_starter(q):
        st.session_state.messages.append({"role": "user", "content": q})
        with st.chat_message("assistant", avatar="🐻"):
            res = get_gemini_response(q)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
        st.rerun()
    with c1:
        if st.button("HPLC 피크 갈라짐 해결방법 알려줘", use_container_width=True): click_starter("HPLC 피크 갈라짐 해결방법 알려줘")
    with c2:
        if st.button("HPLC 결과 재현성이 안 좋아", use_container_width=True): click_starter("HPLC 결과 재현성이 안 좋아")

if prompt := st.chat_input("질문을 입력하세요..."):
    with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
