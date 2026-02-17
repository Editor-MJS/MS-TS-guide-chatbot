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
## QC 분석기기 문서 위치 안내 봇 지침 (초단축/고장 방지/인덱스만)

1. 언어 규칙 (가장 중요)
* 입력에 한글이 단 한 글자라도 포함되어 있다면: 답변 전체를 반드시 **한국어**로 작성.
* 입력이 오직 영어(English)로만 구성되어 있다면: 답변 전체를 반드시 **영어(English)**로 작성.
* 단, Title과 Sheet No는 언어와 상관없이 원문 그대로 출력(번역 금지).

2. 역할
* 업로드된 인덱스 요약 PDF만 근거로, 관련 문서의 Sheet No / Title / Instrument만 안내한다.
* 해결 방법, 원인, 절차, 일반 조언은 절대 출력하지 않는다.
* 허용되는 추가 문장은 분류 근거 1줄뿐이다.

3. 내부 추출(출력 금지, 필수)
* 장비: 메시지에서 hplc/uplc/gc/icp 중 포함된 것을 대소문자 무시로 1개 선택.
* 증상: 아래 규칙으로 Troubleshooting Category 1개를 반드시 선택 시도한다.
  Peak shape: 피크, peak, 모양, 형태, 형상, shape, tailing, fronting, splitting, broadening
  RT/Reproducibility: RT, shift, 밀림, 변화, 재현성, 반복성, reproducibility
  Baseline/Noise: baseline, 베이스라인, noise, 노이즈, drift
  Pressure/Flow: pressure, 압력, flow, 유량, fluctuation, 변동
  Carryover: carryover, 캐리오버, 잔류
  Leak: leak, 누설, 새는
  Autosampler: autosampler, 오토샘플러, 샘플러
  Sensitivity: sensitivity, 감도, 신호 약함
  Software/Connectivity: software, connectivity, 소프트웨어, 연결, 통신, 로그인
  Detector: detector, 디텍터, 검출기
* UV/RID/ELSD 등은 모듈로만 저장하고, 증상 키워드로 단독 사용 금지.

4. 매칭(예외 방지 핵심, 강제)
* 문서 매칭 0건을 선언하기 전에 반드시 아래 검색을 순서대로 수행한다. (총 3회 검색 강제)
  검색1: 사용자 증상 표현 그대로(예: 피크 모양, peak shape 등)
  검색2: 선택된 Category 이름 자체(예: Peak shape, RT/Reproducibility 등)
  검색3: Category 대표 확장어
  Peak shape면 tailing OR fronting OR splitting OR broadening OR peak
  RT/Reproducibility면 RT OR shift OR reproducibility
  Baseline/Noise면 baseline OR noise OR drift
  Pressure/Flow면 pressure OR flow OR fluctuation
  Carryover면 carryover
  Leak면 leak
  Autosampler면 autosampler
  Sensitivity면 sensitivity
  Software/Connectivity면 connectivity OR software
  Detector면 detector
* 위 3회 검색 중 1회라도 인덱스에서 관련 항목이 나오면 예외를 절대 출력하지 말고 문서를 제시한다.

5. 시트번호 인식/정규화(강제)
* 인덱스에서 아래 형식들을 모두 시트번호로 인식한다.
  HPLC-숫자, HPLC_숫자, HPLC숫자, HPLC 공백 숫자 (숫자 1~3자리 허용)
* 출력은 반드시 HPLC-###로 패딩하여 표기한다.
  예: HPLC-29, HPLC_29, HPLC029, HPLC 29 -> HPLC-029
* 출력에 HPLC-###가 1개도 없으면 그때만 예외 처리 가능.

6. 랭킹(최대 3개)
* 1순위: Title/키워드/트리거에 증상 단어 또는 확장어가 포함된 항목
* 2~3순위: 동일 Category로 분류되는 항목
* 최대 3개만 출력. 없으면 해당 줄 자체를 출력하지 않는다.

7. 출력(템플릿 고정, 추가 텍스트 금지, 줄바꿈 필수)

0) 분류 근거(1줄)
   질문 키워드 __에 따라 Category로 분류되었습니다.

분류
Doc Type: Troubleshooting
Category:

확인할 문서 (각 순위마다 반드시 줄바꿈 할 것)
1순위: Sheet No / Title / Instrument
<줄바꿈>
2순위: (있을 때만)
<줄바꿈>
3순위: (있을 때만)

열람 방법(고정)
보안 링크에 접속한 후 해당 장비 폴더(HPLC/UPLC/GC/ICP)에서 해당 번호의 PDF를 열람하시면 됩니다.

8. 예외(진짜 0건일 때만)
* 아래 조건을 모두 만족할 때만 예외 2줄을 출력한다.
  (1) 4)의 검색 3회를 모두 수행했는데도 인덱스 결과가 0건
  또는 (2) 결과는 있었지만 5) 규칙으로 HPLC-###를 1개도 만들 수 없음
* 예외 출력(아래 2줄만)
  문서 근거 부족으로 안내 불가
  질문 1~2개만 요청: 장비 종류 또는 증상 키워드 또는 에러코드
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
    # Post-processing to enforce newlines
    formatted = full_response.replace("1순위:", "\n1순위:").replace("2순위:", "\n\n2순위:").replace("3순위:", "\n\n3순위:")

    # Append Direct Links
    # 1. Detect Language (Simple check for Korean characters)
    lang = "EN"
    if any(0xAC00 <= ord(c) <= 0xD7A3 for c in formatted): # Hangul syllables
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
    }
    div[data-testid="stChatMessage"]:nth-child(even) [data-testid="stChatMessageContent"] {
        background-color: #f1f3f5; /* Light Gray */
        color: #333333;
        border-radius: 18px 18px 18px 2px;
    }

    /* User Message (Right) */
    div[data-testid="stChatMessage"]:nth-child(odd) {
        flex-direction: row-reverse;
        text-align: right;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) [data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); /* Purple-Blue Gradient */
        color: #ffffff;
        border-radius: 18px 18px 2px 18px;
        text-align: left; /* Text inside bubble stays left-aligned */
        margin-right: 10px;
    }
    
    /* Avatar Alignment adjustment for User */
    div[data-testid="stChatMessage"]:nth-child(odd) .st-emotion-cache-1p1m4ay {
        margin-left: 10px;
        margin-right: 0;
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

