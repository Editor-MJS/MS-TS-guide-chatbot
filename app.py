import streamlit as st
import google.generativeai as genai
import os
import re
import pandas as pd
from dotenv import load_dotenv
from utils import get_index_context

# 0. 환경 변수 로드
load_dotenv()

# 1. Gemini API 설정
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Google API Key를 찾을 수 없습니다. .env 파일을 확인해주세요.")
    st.stop()

genai.configure(api_key=api_key)

# 2. 문서 링크 로드 (Excel 최우선)
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
    except Exception:
        pass
    return links

DOCUMENT_LINKS = load_document_links()

# 3. 인공지능 응답 함수
def get_gemini_response(user_prompt):
    # 대화 맥락 구성
    history = ""
    if "messages" in st.session_state:
        for m in st.session_state.messages[-4:]:
            role = "User" if m["role"] == "user" else "Assistant"
            history += f"{role}: {m['content']}\n"

    # 프롬프트 구성 (하나의 문자열로 합쳐서 오류 방지)
    full_text_prompt = f"""
    ## QC 분석기기 지침서 안내 봇
    
    [지침]
    1. 반드시 제공된 INDEX DATA만 근거로 답변할 것.
    2. 위치 정보(Sheet No, Title, Instrument) 외의 조언은 절대 하지 말 것.
    3. 한국어 질문엔 한국어로, 영어 질문엔 영어로 답변할 것.
    4. 출력 형식: [장비명]-[번호3자리] (예: HPLC-029)

    [INDEX DATA]
    {st.session_state.index_context}

    [대화 기록]
    {history}

    [사용자 질문]
    {user_prompt}
    """
    
    # 모델 설정 (가장 안정적인 최신 명칭 사용)
    try:
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        response = model.generate_content(full_text_prompt)
        text = response.text
    except Exception as e:
        # 모델 명칭 호환성 대비 (실패 시 차선책 모델 사용)
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(full_text_prompt)
        text = response.text

    # 링크 매칭 및 포맷팅
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', text)
    unique_links = set()
    link_md = ""
    for inst, num in matches:
        key = (inst.upper(), num, lang)
        if key in DOCUMENT_LINKS:
            url = DOCUMENT_LINKS[key]
            if url not in unique_links:
                label = f"{inst}-{num} 문서 바로가기" if lang == "KR" else f"View Document {inst}-{num}"
                link_md += f"\n\n🔗 [{label}]({url})"
                unique_links.add(url)
    
    footer = "\n\n---\n💡 문서를 못 찾으셨나요? [**전체 폴더 가기**](https://works.do/FYhb6GY)" if lang=="KR" else "\n\n---\n💡 [**Check Entire Folder**](https://works.do/FYhb6GY)"
    return text + link_md + footer

# 4. Streamlit UI
st.set_page_config(page_title="MS·TS Guide Chatbot", page_icon="🐻")

# CSS 디자인
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .header-container {
        background: linear-gradient(135deg, #3B28CC 0%, #E062E6 100%);
        padding: 2.5rem 1.5rem; border-radius: 0 0 20px 20px; color: white; margin-bottom: 2rem;
    }
    [data-testid="stChatMessage"] { border-radius: 15px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-container"><h1>MS·TS Guide Chatbot</h1><p>증상을 입력하시면 관련 지침서 위치를 찾아드립니다.</p></div>', unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "index_context" not in st.session_state:
    st.session_state.index_context = get_index_context()

# 채팅 표시
for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# 스타터 버튼
if not st.session_state.messages:
    st.info("💡 아래 예시를 클릭하거나 질문을 입력하세요.")
    c1, c2 = st.columns(2)
    def fast_query(q):
        st.session_state.messages.append({"role": "user", "content": q})
        with st.chat_message("assistant", avatar="🐻"):
            res = get_gemini_response(q)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
        st.rerun()
    if c1.button("HPLC 피크 갈라짐 해결", use_container_width=True): fast_query("HPLC 피크 갈라짐 해결방법 알려줘")
    if c2.button("HPLC 재현성이 안 좋아", use_container_width=True): fast_query("HPLC 결과 재현성이 안 좋아")

# 채팅 입력
if prompt := st.chat_input("증상을 입력하세요..."):
    with st.chat_message("user", avatar="🧑‍💻"): st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
