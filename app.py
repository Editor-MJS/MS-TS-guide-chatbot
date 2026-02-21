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
  "temperature": 0.1, # Slightly increased for better flexibility
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

# Load Document Links
def load_document_links():
    links = {}
    try:
        # Check both local and parent for CSV
        csv_path = 'document_links.csv'
        if not os.path.exists(csv_path):
            csv_path = os.path.join('..', 'document_links.csv')
            
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
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
* 업로드된 인덱스만 근거로, 관련 문서의 Sheet No / Title / Instrument만 안내한다.
* 해결 방법, 원인, 절차, 일반 조언은 절대 출력하지 않는다.
* 허용되는 추가 문장은 분류 근거 1줄뿐이다.

3. 내부 추출(출력 금지, 필수)
* 장비: 메시지에서 언급된 분석 기기 명칭(HPLC, UPLC, GC, ICP 등)을 추출한다. 인덱스에 새로운 장비가 추가되어도 해당 명칭을 인식해야 한다.
* 증상: 아래 규칙으로 Troubleshooting Category 1개를 반드시 선택 시도한다. (모든 장비에 공통 적용)
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
* 특정 기기 전용 모듈(UV, RID, ELSD 등)은 참고 정보로만 활용한다.

4. 매칭(예외 방지 핵심, 강제)
* 문서 매칭 0건을 선언하기 전에 반드시 아래 검색을 순서대로 수행한다. (총 3회 검색 강제)
  검색1: 사용자 증상 표현 그대로
  검색2: 선택된 Category 이름 자체
  검색3: Category 대표 확장어
* 위 3회 검색 중 1회라도 인덱스에서 관련 항목이 나오면 예외를 절대 출력하지 말고 문서를 제시한다.

5. 시트번호 인식/정규화(강제)
* 출력은 반드시 [장비명]-[###] 형식으로 패딩하여 표기한다. (예: HPLC-029)

6. 랭킹(최대 3개)
* 최대 3개만 출력. 없으면 해당 줄 자체를 출력하지 않는다.

7. 출력(템플릿 고정, 추가 텍스트 금지, 줄바꿈 필수)

0) 분류 근거(1줄)
   질문 키워드 __에 따라 Category로 분류되었습니다.

분류
Doc Type: Troubleshooting
Category:

확인할 문서
1순위: Sheet No / Title / Instrument
<줄바꿈>
2순위: (있을 때만)
<줄바꿈>
3순위: (있을 때만)

열람 방법
보안 링크에 접속한 후 해당 장비 폴더에서 해당 번호의 PDF를 열람하시면 됩니다.

8. 대화 맥락 유지 (Context Awareness)
* 사용자가 "더 알려줘", "다른 방법 없어?" 등 추가 정보를 요청하면, 이전 대화의 장비/증상 정보를 유지하여 문서를 다시 검색한다.

9. 전체 문서함 안내 (Global Folder Link)
* 사용자가 "전체 문서", "폴더 링크" 등을 요청할 때만 아래 링크를 안내한다.
* 전체 문서함 링크: https://works.do/FYhb6GY
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
        f"\n\n--- INDEX DATA START ---\n{st.session_state.index_context}\n--- INDEX DATA END ---\n",
        f"\n--- CONVERSATION HISTORY START ---\n{conversation_history}\n--- CONVERSATION HISTORY END ---\n",
        f"User Question: {user_prompt}"
    ]
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(full_prompt, generation_config=generation_config)
    
    full_response = response.text
    formatted = full_response.replace("1순위:", "\n1순위:").replace("2순위:", "\n\n2순위:").replace("3순위:", "\n\n3순위:")

    lang = "EN"
    if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt): 
        lang = "KR"
    
    matches = re.findall(r'([A-Za-z]+)-(\d{3})', formatted, re.IGNORECASE)
    
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
    
    if lang == "KR":
        global_link = "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함(폴더)**](https://works.do/FYhb6GY)에서 직접 확인하실 수 있습니다."
    else:
        global_link = "\n\n---\n💡 Can't find what you're looking for? You can check the [**Entire Folder**](https://works.do/FYhb6GY) directly."
    
    return formatted + link_markdown + global_link

# Streamlit UI
st.set_page_config(page_title="MS·TS guide chatbot (Trial)", page_icon="🐻", layout="centered")

# Custom CSS for Premium Design
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@300;400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .stApp { background-color: #ffffff; }
    header {visibility: hidden;}
    .header-container {
        background: linear-gradient(135deg, #3B28CC 0%, #E062E6 100%);
        padding: 3rem 2rem;
        border-radius: 0 0 25px 25px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    [data-testid="stChatMessage"]:nth-child(even) [data-testid="stChatMessageContent"] {
        background-color: #f1f3f5 !important;
        border-radius: 18px 18px 18px 2px !important;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) {
        flex-direction: row-reverse !important;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) [data-testid="stChatMessageContent"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: #ffffff !important;
        border-radius: 18px 18px 2px 18px !important;
        text-align: left !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-container">
    <div class="header-title" style="font-size:2.2rem; font-weight:700;">MS·TS Trial Chatbot</div>
    <div class="header-subtitle" style="opacity:0.9;">JSON 인덱스 기반 자동화 실험 버전입니다.</div>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "index_context" not in st.session_state:
    with st.spinner("JSON 지식을 불러오는 중입니다..."):
        st.session_state.index_context = get_index_context()

for message in st.session_state.messages:
    avatar = "🐻" if message["role"] == "assistant" else "🧑‍💻"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

if len(st.session_state.messages) == 0:
    st.markdown("<div style='color: #888; font-size: 0.9rem; margin-bottom: 10px;'>💡 테스트 질문</div>", unsafe_allow_html=True)
    if st.button("HPLC 피크 갈라짐 해결방법 알려줘", use_container_width=True):
        st.session_state.messages.append({"role": "user", "content": "HPLC 피크 갈라짐 해결방법 알려줘"})
        st.rerun()

if prompt := st.chat_input("테스트 질문을 입력하세요"):
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant", avatar="🐻"):
        response = get_gemini_response(prompt)
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
