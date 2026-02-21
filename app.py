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

# 1. 문서 링크 로드 (CSV 방식)
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

# 2. 사진 속 그 답변을 만드는 '똑똑한 시스템 지침'
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침 (Troubleshooting 전문)

1. 언어 규칙 (가장 중요)
* 입력에 한글이 한 글자라도 포함되어 있다면: 답변 전체를 반드시 **한국어**로 작성.
* 입력이 오직 영어(English)로만 구성되어 있다면: 답변 전체를 반드시 **영어(English)**로 작성.
* 단, Title과 Sheet No는 언어와 상관없이 원문 그대로 출력(번역 금지).

2. 역할
* 업로드된 인덱스 PDF만 근거로, 관련 문서의 Sheet No / Title / Instrument만 안내한다.
* 해결 방법, 원인, 절차, 일반 조언은 절대 출력하지 않는다.

3. 증상 분류 (Category 강제 선택)
* 메시지를 분석하여 하나를 선택: Peak shape, RT/Reproducibility, Baseline/Noise, Pressure/Flow, Carryover, Leak, Autosampler, Sensitivity, Software/Connectivity, Detector.

4. 출력 템플릿 (사진과 동일하게 고정)
0) 분류 근거
The question keyword '__' has been classified into the 'Category' Category.

분류
Doc Type: Troubleshooting
Category:

확인할 문서
1순위: Sheet No / Title / Instrument
2순위: (있을 때만)
3순위: (있을 때만)

열람 방법
보안 링크에 접속한 후 해당 장비 폴더(HPLC/UPLC/GC/ICP)에서 해당 번호의 PDF를 열람하시면 됩니다.
"""

def get_gemini_response(user_prompt):
    full_prompt = f"{SYSTEM_PROMPT}\n\n[INDEX DATA]\n{st.session_state.index_context}\n\n[USER QUESTION]\n{user_prompt}"
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
                label = f"Open {inst}-{num}" if lang == "EN" else f"{inst}-{num} 문서 바로가기"
                link_md += f"\n\n🔗 [{label}]({url})"
                unique_links.add(url)
    
    footer = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함(폴더)**](https://works.do/FYhb6GY)에서 직접 확인하실 수 있습니다."
    return text + link_md + footer

# 3. 프리미엄 UI 디자인 (보라색 헤더 복구)
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

# 스타터 버튼 2개 복구 (사진과 동일하게)
if not st.session_state.messages:
    st.markdown("<div style='color: #888; font-size: 0.9rem; margin-bottom: 10px;'>💡 테스트 질문</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    def click(txt):
        st.session_state.messages.append({"role": "user", "content": txt})
        with st.chat_message("assistant", avatar="🐻"):
            res = get_gemini_response(txt)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
        st.rerun()
    with c1:
        if st.button("HPLC 피크 갈라짐 해결방법 알려줘", use_container_width=True): click("HPLC 피크 갈라짐 해결방법 알려줘")
    with c2:
        if st.button("HPLC 결과 재현성이 안 좋아", use_container_width=True): click("HPLC 결과 재현성이 안 좋아")

if prompt := st.chat_input("질문을 입력하세요..."):
    with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
