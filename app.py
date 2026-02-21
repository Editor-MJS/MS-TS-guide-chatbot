import streamlit as st
import google.generativeai as genai
import os
import re
import pandas as pd
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

# Generation Config
generation_config = {
  "temperature": 0.1,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

# Load Document Links from Excel
def load_document_links():
    links = {}
    try:
        # Check both local and parent for Excel
        excel_path = 'document_links.xlsx'
        if not os.path.exists(excel_path):
            excel_path = os.path.join('..', 'document_links.xlsx')
            
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            for _, row in df.iterrows():
                # Expected columns: equipment, sheet_no, language, link
                equipment = str(row['equipment']).upper()
                sheet_no = str(row['sheet_no']).strip()
                
                # Handle cases where sheet_no might be read as float (e.g., 30.0)
                if '.' in sheet_no:
                    sheet_no = sheet_no.split('.')[0].zfill(3)
                else:
                    try:
                        sheet_no = str(int(float(sheet_no))).zfill(3)
                    except:
                        sheet_no = sheet_no.zfill(3)
                
                language = str(row['language']).upper()
                link = str(row['link']).strip()
                
                key = (equipment, sheet_no, language)
                if link and link != 'nan':
                    links[key] = link
        else:
            # Fallback for local testing if xlsx is missing
            st.warning("document_links.xlsx 파일을 찾을 수 없습니다. 엑셀 파일을 생성해주세요.")
    except Exception as e:
        st.error(f"Excel 링크 로딩 오류: {e}")
        return {}
    return links

DOCUMENT_LINKS = load_document_links()

# System Prompt
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침 (초단축/고장 방지/인덱스만)

1. 언어 규칙 (가장 중요)
* 입력에 한글이 단 한 글자라도 포함되어 있다면: 답변 전체를 반드시 **한국어**로 작성.
* 입력이 오직 영어(English)로만 구성되어 있다면: 답변 전체를 반드시 **영어(English)**로 작성.
* 단, Title과 Sheet No는 언어와 상관없이 원문 그대로 출력(번역 금지).

2. 역할
* 업로드된 인덱스만 근거로, 관련 문서의 Sheet No / Title / Instrument만 안내한다.
* 해결 방법, 원인, 절차, 일반 조언은 절대 출력하지 않는다.
* 허용되는 추가 문장은 분류 근거 1줄뿐이다.

3. 내부 추출(출력 금지, 필수)
* 장비: 메시지에서 언급된 분석 기기 명칭(HPLC, UPLC, GC, ICP 등)을 추출한다. 인덱스에 새로운 장비가 추가되어도 해당 명칭을 인식해야 한다.
* 증상: 모든 장비에 공용 카테고리를 적용한다.

4. 매칭(강제)
* 문서 매칭 0건을 선언하기 전에 3회 검색을 수행한다.

5. 템플릿
분류 근거
확인할 문서 (1순위~3순위)
전체 문서함 링크
"""

def get_gemini_response(user_prompt):
    conversation_history = ""
    if "messages" in st.session_state and len(st.session_state.messages) > 0:
        recent_msgs = st.session_state.messages[-4:]
        for msg in recent_msgs:
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_history += f"{role}: {msg['content']}\n"

    full_prompt = [
        SYSTEM_PROMPT,
        f"\n--- INDEX DATA ---\n{st.session_state.index_context}\n",
        f"\n--- HISTORY ---\n{conversation_history}\n",
        f"User Question: {user_prompt}"
    ]
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(full_prompt, generation_config=generation_config)
    
    formatted = response.text.replace("1순위:", "\n1순위:").replace("2순위:", "\n\n2순위:").replace("3순위:", "\n\n3순위:")
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', formatted, re.IGNORECASE)
    link_markdown = ""
    unique_links = set()
    for inst, num in matches:
        key = (inst.upper(), num, lang)
        if key in DOCUMENT_LINKS:
            url = DOCUMENT_LINKS[key]
            if url not in unique_links:
                link_markdown += f"\n\n🔗 [{inst}-{num} 문서 바로가기]({url})" if lang=="KR" else f"\n\n🔗 [Open {inst}-{num}]({url})"
                unique_links.add(url)
    
    global_link = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함**](https://works.do/FYhb6GY)" if lang=="KR" else "\n\n---\n💡 Check the [**Entire Folder**](https://works.do/FYhb6GY)"
    return formatted + link_markdown + global_link

# UI
st.set_page_config(page_title="MS·TS Chatbot (Excel Ver)", page_icon="🐻", layout="centered")

# CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .header-container {
        background: linear-gradient(135deg, #3B28CC 0%, #E062E6 100%);
        padding: 2rem; border-radius: 0 0 20px 20px; color: white; margin-bottom: 2rem;
    }
    [data-testid="stChatMessage"]:nth-child(even) [data-testid="stChatMessageContent"] { background-color: #f1f3f5 !important; border-radius: 15px; }
    div[data-testid="stChatMessage"]:nth-child(odd) { flex-direction: row-reverse !important; }
    div[data-testid="stChatMessage"]:nth-child(odd) [data-testid="stChatMessageContent"] { 
        background: linear-gradient(135deg, #667eea, #764ba2) !important; color: white !important; border-radius: 15px; 
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-container"><h1>MS·TS Guide (Excel)</h1></div>', unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "index_context" not in st.session_state: st.session_state.index_context = get_index_context()

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

if prompt := st.chat_input("질문을 입력하세요"):
    st.chat_message("user", avatar="🧑‍💻").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
