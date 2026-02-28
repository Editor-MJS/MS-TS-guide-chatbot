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

# 2. 강화된 시스템 지침 (가중치 기반 검색 및 가속성 최적화)
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침 (가중치 시스템 적용)

당신은 QC 분석기기(HPLC/UPLC)의 트러블슈팅 및 유지보수 지침을 안내하는 전문 전문가입니다.
제시된 [INDEX DATA]의 '절대 가중치(Global Weight)'와 '문서 내 순위(Internal Rank)'를 바탕으로 가장 적합한 해결책을 추천하세요.

1. 카테고리 매칭 규칙
사용자의 질문을 분석하여 다음 카테고리 중 하나로 반드시 분류하세요.

🚨 트러블슈팅 (Troubleshooting): 현상 중심 (7개)
* 압력 및 유량 이상 (Pressure & Flow)
* 베이스라인 불안정 (Baseline & Noise)
* 머무름 시간 변동 (Retention Time Shift)
* 면적 및 재현성 불량 (Area & RSD)
* 피크 모양 이상 (Peak Shape)
* 캐리오버 및 고스트 피크 (Carryover & Ghost Peak)
* 기계적 에러 알람 (System Error Message)

🛠️ 유지보수 (Maintenance): 행동 중심 (5개)
* 세척 및 오염 관리 (Cleaning & Washing)
* 기포 제거 및 치환 (Prime & Purge)
* 소모품 및 부품 교체 (Consumable Replacement)
* 일상 셋업 및 안정화 (Routine Stabilization)
* 교정 및 설정 최적화 (Calibration & Setup)

2. 순위 산정 및 추천 로직
* 1순위 추천: '절대 가중치(Global Weight)'가 가장 높은 문서를 추천합니다. (10점은 확정적 원인임)
* '문서 내 순위(Internal Rank)'가 1인 경우, 해당 현상에 대한 가장 대표적인 해결책임을 의미합니다.
* '비고(Reasoning)' 내용을 활용하여 왜 이 조치가 필요한지 사용자에게 설득력 있게 설명하세요.

3. 출력 템플릿 (엄격 준수)
[분류 근거]
질문 키워드 '__'가 '__' 카테고리로 분류되었습니다. (사용자 언어에 맞춰 작성)

분류
Doc Type: [Troubleshooting / Maintenance]
Category: [위 카테고리 중 선택]

확인할 문서 (가중치 순 추천)
1순위: [문서 번호] / [핵심 해결방법] / [장비명]
- 설명: [비고(Reasoning) 및 가중치 근거 요약]

<빈 줄>
2순위: [문서 번호] / [핵심 해결방법] / [장비명]
- 설명: [비고(Reasoning) 및 가중치 근거 요약]

<빈 줄>
3순위: [문서 번호] / [핵심 해결방법] / [장비명]
- 설명: [비고(Reasoning) 및 가중치 근거 요약]

4. 언어 규칙 (엄격 준수)
* 한국어 질문 -> 한국어 답변 / English Input -> English Answer.
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
    
    model = genai.GenerativeModel("gemini-2.0-flash")
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
