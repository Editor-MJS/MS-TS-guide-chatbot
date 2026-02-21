import streamlit as st
import google.generativeai as genai
import os
import re
import pandas as pd
from dotenv import load_dotenv
from utils import get_index_context

# 0. Load environment variables
load_dotenv()

# 1. Configure Gemini API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    st.error("Google API Key not found. Please set it in .env file.")
    st.stop()

genai.configure(api_key=api_key)

# Generation Config (Keep temperature low for precision)
generation_config = {
  "temperature": 0.1,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

# 2. Load Document Links from Excel (Premium Managed)
def load_document_links():
    links = {}
    try:
        # Check both local and parent for Excel (for flexibility)
        excel_path = 'document_links.xlsx'
        if not os.path.exists(excel_path):
            excel_path = os.path.join(os.path.dirname(__file__), '..', 'document_links.xlsx')
            
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            for _, row in df.iterrows():
                # Columns: equipment, sheet_no, language, link
                inst = str(row['equipment']).upper().strip()
                # Normalize sheet_no to 3 digits
                raw_num = str(row['sheet_no']).strip()
                if '.' in raw_num: raw_num = raw_num.split('.')[0]
                num = raw_num.zfill(3)
                
                lang = str(row['language']).upper().strip()
                url = str(row['link']).strip()
                
                if url and url != 'nan':
                    links[(inst, num, lang)] = url
    except Exception as e:
        return {} # Silent fail in production
    return links

DOCUMENT_LINKS = load_document_links()

# 3. Robust System Prompt (The Heart of Chatbot)
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침 (Ultimate v2)

1. 언어 규칙
* 입력에 한글이 포함되어 있으면 반드시 **한국어**로 답변.
* 입력이 영어로만 되어 있으면 반드시 **영어**로 답변.
* Title과 Sheet No는 번역하지 않고 원문 그대로 출력.

2. 역할 및 제약
* 제공된 인덱스 데이터만 근거로 한다.
* 해결 방법이나 절차는 안내하지 않고 오직 **문서의 위치(Sheet No / Title / Instrument)**만 안내한다.

3. 매칭 및 검색 (강제 3회 검색)
* 사용자 증상에서 장비와 키워드(Peak, RT, Baseline, Pressure 등)를 추출한다.
* 인덱스에 새로운 장비(UPLC, GC, ICP 등)가 추가되어도 그 명칭을 인식해야 한다.
* 1순위: 증상이 포함된 문서 / 2~3순위: 관련 카테고리 문서.

4. 시트번호 출력 형식
* 반드시 [장비명]-[번호3자리] 형식으로 출력. (예: HPLC-029, UPLC-005)

5. 출력 템플릿 (고정)
분류 근거: __ 키워드에 따라 __ 카테고리로 분류되었습니다.

확인할 문서
1순위: [번호] / [제목] / [장비명]
2순위: (있을 때만)
3순위: (있을 때만)

열람 방법: 보안 링크 접속 후 해당 장비 폴더에서 위 번호의 파일을 열람하세요.
"""

def get_gemini_response(user_prompt):
    conversation_history = ""
    if "messages" in st.session_state:
        recent = st.session_state.messages[-4:]
        for m in recent:
            role = "User" if m["role"] == "user" else "Assistant"
            conversation_history += f"{role}: {m['content']}\n"

    full_prompt = [
        SYSTEM_PROMPT,
        f"\n--- INDEX DATA ---\n{st.session_state.index_context}\n",
        f"\n--- CONVERSATION HISTORY ---\n{conversation_history}\n",
        f"User Question: {user_prompt}"
    ]
    
    model = genai.GenerativeModel("gemini-1.5-flash") # Use stable model
    response = model.generate_content(full_prompt, generation_config=generation_config)
    
    formatted = response.text.replace("1순위:", "\n1순위:").replace("2순위:", "\n\n2순위:").replace("3순위:", "\n\n3순위:")
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    
    # Extract Document Links
    links_text = ""
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', formatted)
    unique_links = set()
    for inst, num in matches:
        key = (inst.upper(), num, lang)
        if key in DOCUMENT_LINKS:
            url = DOCUMENT_LINKS[key]
            if url not in unique_links:
                label = f"{inst}-{num} 문서 바로가기" if lang == "KR" else f"Direct Link: {inst}-{num}"
                links_text += f"\n\n🔗 [{label}]({url})"
                unique_links.add(url)
    
    # Global Footer
    if lang == "KR":
        footer = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함(폴더)**](https://works.do/FYhb6GY)에서 직접 확인하실 수 있습니다."
    else:
        footer = "\n\n---\n💡 Can't find it? Check the [**Entire Folder**](https://works.do/FYhb6GY) directly."
        
    return formatted + links_text + footer

# 4. Streamlit UI (Restore Premium Theme)
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
    <div style="opacity: 0.9; font-weight: 300;">증상이나 문제를 입력하면 관련 문서를 안내해드립니다.</div>
</div>
""", unsafe_allow_html=True)

# Session States
if "messages" not in st.session_state: st.session_state.messages = []
if "index_context" not in st.session_state:
    with st.spinner("지식 베이스를 불어오는 중입니다..."):
        st.session_state.index_context = get_index_context()

# Display Chat
for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# Starters (Restore!)
if len(st.session_state.messages) == 0:
    st.markdown("<div style='color:#888; font-size:0.9rem; margin-bottom:10px;'>💡 예시 질문을 클릭해보세요</div>", unsafe_allow_html=True)
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

# Chat Input
if prompt := st.chat_input("증상을 입력해주세요 (예: HPLC 피크 모양이 이상해)"):
    st.chat_message("user", avatar="🧑‍💻").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("assistant", avatar="🐻"):
        res = get_gemini_response(prompt)
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})
