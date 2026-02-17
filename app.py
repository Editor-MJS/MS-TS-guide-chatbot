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

# Generation Config
generation_config = {
  "temperature": 0.0, # Low temperature for strict rule following
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
  "max_output_tokens": 8192,
}

# Load Document Links
def load_document_links():
    links = {}
    try:
        with open('document_links.csv', mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Key: (EQUIPMENT, SHEET_NO, LANGUAGE)
                # Ensure sheet_no is 3 digits if needed, but CSV already has 030
                key = (row['equipment'].upper(), row['sheet_no'], row['language'].upper())
                if row['link'] and row['link'].strip():
                    links[key] = row['link'].strip()
    except Exception:
        return {} # Fail silently if file missing
    return links

DOCUMENT_LINKS = load_document_links()

# System Prompt (User's Instruction)
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침

1. 언어 & 템플릿 규칙 (절대 준수)
* 사용자의 질문(입력) 언어를 감지하여 반드시 아래 두 가지 템플릿 중 하나만 선택해라.

[Case A: 한국어 질문일 때]
0) 분류 근거(1줄)
   질문 키워드 __에 따라 Category로 분류되었습니다.

분류
Doc Type: Troubleshooting
Category: <Category Name>

확인할 문서
1순위: <Sheet No> / <Title> / <Instrument>
<줄바꿈>
2순위: (있을 때만)
<줄바꿈>
3순위: (있을 때만)

열람 방법
보안 링크에 접속한 후 해당 장비 폴더(HPLC/UPLC/GC/ICP)에서 해당 번호의 PDF를 열람하시면 됩니다.

[Case B: English Question]
0) Reasoning (1 line)
   Classified into <Category Name> category based on keyword __.

Classification
Doc Type: Troubleshooting
Category: <Category Name>

Recommended Documents
Rank 1: <Sheet No> / <Title> / <Instrument>
<New Line>
Rank 2: (If available)
<New Line>
Rank 3: (If available)

How to Access
Please access the secure link and open the PDF with the corresponding number in the equipment folder (HPLC/UPLC/GC/ICP).

2. 역할
* 업로드된 인덱스만 근거로, Sheet No / Title / Instrument 안내.
* 해결 방법/원인 등 추가 설명 금지.

3. 내부 추출 (Internal Logic)
* 장비: hplc, uplc, gc, icp (case insensitive)
* 증상(Category):
  Peak shape, RT/Reproducibility, Baseline/Noise, Pressure/Flow, Carryover, Leak, Autosampler, Sensitivity, Software/Connectivity, Detector

4. 매칭 규칙 (Matching)
* 3단계 검색(증상 키워드 -> 카테고리명 -> 확장어) 수행 필수.
* 하나라도 매칭되면 문서 제시.

5. Sheet No
* HPLC-### 형식 준수 (예: HPLC-029).

6. 예외 (Exception)
* [KR]: 문서 근거 부족으로 안내 불가\n질문 1~2개만 요청: 장비 종류 또는 증상 키워드
* [EN]: Unable to provide guidance due to lack of document basis.\nPlease ask with Equipment type or Symptom keyword.
"""

def get_gemini_response(user_prompt):
    full_prompt = [
        SYSTEM_PROMPT,
        f"\n\n--- INDEX DATA START ---\n{st.session_state.index_context}\n--- INDEX DATA END ---\n",
        f"User Question: {user_prompt}"
    ]
    
    model = genai.GenerativeModel("gemini-2.5-flash") # Upgraded to 2.5-flash
    response = model.generate_content(full_prompt, generation_config=generation_config)
    
    full_response = response.text
    full_response = response.text
    # Post-processing to enforce newlines
    formatted = full_response.replace("1순위:", "\n1순위:").replace("2순위:", "\n\n2순위:").replace("3순위:", "\n\n3순위:")
    formatted = formatted.replace("Rank 1:", "\nRank 1:").replace("Rank 2:", "\n\nRank 2:").replace("Rank 3:", "\n\nRank 3:")

    # Append Direct Links
    # 1. Detect Language (Check USER INPUT for Korean)
    # If user input has ANY Korean -> Show KR links.
    # If user input is ONLY English -> Show EN links.
    lang = "EN"
    if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt): # Hangul syllables in INPUT
        lang = "KR"
    
    # 2. Extract Document IDs (e.g., HPLC-029)
    # Pattern matches HPLC-029, UPLC-001, etc.
    matches = re.findall(r'(HPLC|UPLC|GC|ICP)-(\d{3})', formatted, re.IGNORECASE)
    
    unique_links = set()
    link_markdown = ""
    
    for inst, num in matches:
        key = (inst.upper(), num, lang)
        if key in DOCUMENT_LINKS:
            url = DOCUMENT_LINKS[key]
            if url not in unique_links:
                if lang == "KR":
                    link_markdown += f"\n\n🔗 [{inst}-{num} 문서 바로가기]({url})"
                else:
                    link_markdown += f"\n\n🔗 [Open {inst}-{num}]({url})"
                unique_links.add(url)
    
    return formatted + link_markdown

# Streamlit UI
st.set_page_config(page_title="MS·TS guide chatbot", page_icon="🐻", layout="centered")

# Custom CSS for Premium Design & Gradient Header
st.markdown("""
<style>
    /* Global Font & Reset */
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', sans-serif;
        color: #333333;
    }

    /* Main Background */
    .stApp {
        background-color: #ffffff;
    }

    /* Hide default Streamlit Header */
    header {visibility: hidden;}

    /* Premium Gradient Header Container */
    .header-container {
        background: linear-gradient(135deg, #2b5876 0%, #4e4376 100%);  /* Deep Blue/Purple Gradient */
        /* Alternative brighter gradient matching image: */
        background: linear-gradient(135deg, #3B28CC 0%, #E062E6 100%);
        padding: 3rem 2rem;
        border-radius: 0 0 25px 25px;
        color: white;
        margin-bottom: 2rem;
        text-align: left;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    .header-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .header-subtitle {
        font-size: 1rem;
        opacity: 0.9;
        font-weight: 300;
    }

    /* Chat Message Styling */
    [data-testid="stChatMessage"] {
        background-color: transparent;
        padding: 1rem 0;
    }
    
    /* Avatar Styling */
    [data-testid="stChatMessage"] .st-emotion-cache-1p1m4ay {
        border-radius: 50%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    /* Message Bubbles */
    [data-testid="stChatMessageContent"] {
        padding: 1rem 1.2rem;
        border-radius: 18px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        font-size: 0.95rem;
        line-height: 1.5;
        max-width: 85%;
    }

    /* Assistant Message (Left) */
    div[data-testid="stChatMessage"]:nth-child(even) {
        flex-direction: row;
        justify-content: flex-start;
    }
    div[data-testid="stChatMessage"]:nth-child(even) .stChatMessageContent {
        background-color: #f1f3f5;
        color: #333333;
        border-radius: 18px 18px 18px 2px;
    }

    /* User Message (Right) */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        flex-direction: row-reverse;
        justify-content: flex-end;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) .stChatMessageContent {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #ffffff;
        border-radius: 18px 18px 2px 18px;
        text-align: left;
    }
    
    /* Ensure only the message content gets the background, not the container */
    div[data-testid="stChatMessage"] {
        background-color: transparent !important;
    }
    
    /* Avatar margins */
    div[data-testid="stChatMessage"]:nth-child(odd) .st-emotion-cache-1p1m4ay {
        margin-left: 10px;
    }
    
    /* Fix text color in user bubble for markdown links/bold */
    div[data-testid="stChatMessage"]:nth-child(odd) [data-testid="stChatMessageContent"] p,
    div[data-testid="stChatMessage"]:nth-child(odd) [data-testid="stChatMessageContent"] strong {
        color: #ffffff !important;
    }

    /* Conversation Starters */
    .starter-header {
        font-size: 0.9rem;
        color: #888;
        margin-bottom: 10px;
        margin-top: 20px;
    }
    
    /* Input Area Styling */
    .stChatInputContainer {
        padding-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Custom Header Display
st.markdown("""
<div class="header-container">
    <div class="header-title">MS·TS guide chatbot</div>
    <div class="header-subtitle">증상이나 문제를 입력하면 관련된 문서를 안내해드립니다.</div>
</div>
""", unsafe_allow_html=True)


# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize Context (Load PDF only once)
if "index_context" not in st.session_state:
    with st.spinner("문서 인덱스를 불러오는 중입니다..."):
        st.session_state.index_context = get_index_context()

# Display Chat History
for message in st.session_state.messages:
    # Set avatars: Orange Bear for assistant, default for user
    if message["role"] == "assistant":
        avatar = "🐻" 
    else:
        avatar = "🧑‍💻"
        
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Conversation Starters (Only show if history is empty)
if len(st.session_state.messages) == 0:
    st.markdown("<div class='starter-header'>💡 예시 질문을 클릭해보세요</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    
    # Helper to handle button click
    def handle_starter_click(text):
        st.session_state.messages.append({"role": "user", "content": text})
        with st.spinner("답변을 생성하는 중입니다..."):
            try:
                response = get_gemini_response(text)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                st.session_state.messages.append({"role": "assistant", "content": f"오류 발생: {str(e)}"})
        st.rerun()

    with col1:
        if st.button("HPLC 피크 갈라짐 해결방법 알려줘", use_container_width=True):
            handle_starter_click("HPLC 피크 갈라짐 해결방법 알려줘")
    with col2:
        if st.button("GC 바탕선이 흔들려", use_container_width=True):
            handle_starter_click("GC 바탕선이 흔들려")

# Chat Input
if prompt := st.chat_input("증상을 입력해주세요 (예: HPLC 피크 모양이 이상해)"):
    # Display user message
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Generate Response
    with st.chat_message("assistant", avatar="🐻"):
        message_placeholder = st.empty()
        
        try:
            full_response = get_gemini_response(prompt)
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            error_message = f"오류가 발생했습니다: {str(e)}"
            message_placeholder.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})

