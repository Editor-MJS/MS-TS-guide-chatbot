import streamlit as st
import google.generativeai as genai
import os
import csv
import re
import random
import json
from dotenv import load_dotenv
from utils import get_vector_db

# 0. 초기 설정
load_dotenv()

def get_all_api_keys():
    keys = []
    # Streamlit Secrets (Cloud)
    try:
        for k in st.secrets:
            if "GOOGLE_API_KEY" in k:
                val = st.secrets[k]
                if val: keys.append(val)
    except: pass
    # Environment Variables (Local)
    for env_key in os.environ:
        if "GOOGLE_API_KEY" in env_key:
            val = os.getenv(env_key)
            if val and val not in keys: keys.append(val)
    return list(set(keys)) # 중복 제거

API_KEYS = get_all_api_keys()
if not API_KEYS:
    st.error("Google API Key를 찾을 수 없습니다. .env 파일에 GOOGLE_API_KEY_1, _2 등을 등록해주세요.")
    st.stop()

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

# 2. 강화된 시스템 지침 (가중치 및 벡터 DB 최적화)
SYSTEM_PROMPT = """
## QC 분석기기 문서 위치 안내 봇 지침 (가중치 시스템 적용)

당신은 QC 분석기기(HPLC/UPLC)의 트러블슈팅 및 유지보수 지침을 안내하는 전문 전문가입니다.
제시된 [RETRIEVED DATA]는 사용자의 질문과 의미상 가장 유사한 상위 5개의 문서입니다.
이 데이터의 'Weight(절대 가중치)'와 'InternalRank(문서 내 순위)'를 최우선으로 고려하여 가장 적합한 해결책을 추천하세요.

1. 카테고리 매칭 규칙
사용자의 질문을 분석하여 다음 카테고리 중 하나로 반드시 분류하세요. (대화에는 분류된 카테고리명만 노출)
- 트러블슈팅: 압력 및 유량 이상, 베이스라인 불안정, 머무름 시간 변동, 면적 및 재현성 불량, 피크 모양 이상, 캐리오버 및 고스트 피크, 기계적 에러 알람
- 유지보수: 세척 및 오염 관리, 기포 제거 및 치환, 소모품 및 부품 교체, 일상 셋업 및 안정화, 교정 및 설정 최적화

2. 추천 로직
* 제공된 [RETRIEVED DATA] 안에서 'Weight'가 높은 순서대로 답변을 구성합니다.
* 반드시 데이터에 있는 'DocNo'(예: UPLC_001, HPLC-018)를 변형 없이 사용하세요.
* 'Reasoning(비고/설명)' 내용을 자연스럽게 풀어내어 사용자에게 조치 근거를 설명하세요.

3. 출력 형식 (JSON 형식으로 답변하여 파싱 가능하게 함)
반드시 다음 구조의 JSON 형식으로만 답변하세요:
{
  "classification": "카테고리명",
  "reason": "분류 근거 설명",
  "type": "Troubleshooting/Maintenance",
  "recommendations": [
    {"no": "문서번호", "fix": "해결방법", "instrument": "장비명", "reasoning": "설명/근거", "weight": 점수},
    ... 관련 있는 문서들(최대 5개)을 가중치 순으로 나열 ...
  ]
}
"""

def get_gemini_response(user_prompt):
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    
    if st.session_state.vector_db is None:
        return "⚠️ 데이터베이스가 초기화되지 않았습니다. 관리자에게 문의하세요."
        
    # [핵심] 상위 8개 추출하여 답변 품질과 토큰 사용량 균형 조정
    retrieved_docs = st.session_state.vector_db.similarity_search(user_prompt, k=8)
    
    retrieved_context = "## [RETRIEVED DATA]\n"
    for d in retrieved_docs:
        m = d.metadata
        retrieved_context += f"- DocNo: {m.get('doc_no')} | Fix: {m.get('fix')} | Symptom: {m.get('symptom')} | InternalRank: {m.get('rank')} | Weight: {m.get('weight')} | Reasoning: {m.get('reasoning')}\n"
    
    full_prompt = f"{SYSTEM_PROMPT}\n{retrieved_context}\n\n[USER QUESTION]\n{user_prompt}"
    
    # 모델 후보군 (2.5 Flash Lite부터 구형까지)
    models_to_try = [
        "gemini-2.5-flash-lite", 
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash", 
        "gemini-1.5-flash", 
        "gemini-1.5-flash-8b"
    ]
    
    # API 키 리스트를 무작위로 섞어서 부하 분산
    current_keys = API_KEYS.copy()
    random.shuffle(current_keys)
    
    last_error = ""
    
    # 키 로테이션 + 모델 폴백 (이중 루프 방어막)
    for api_key in current_keys:
        genai.configure(api_key=api_key)
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(full_prompt, generation_config={"response_mime_type": "application/json"})
                
                resp_json = response.text
                # JSON 태그 제거 (Markdown 방지)
                if resp_json.startswith("```json"):
                    resp_json = resp_json.replace("```json", "").replace("```", "").strip()
                
                data = json.loads(resp_json)
                
                st.session_state.current_recommendations = data.get('recommendations', [])
                st.session_state.current_page = 0
                st.session_state.current_classification = data.get('classification', '')
                st.session_state.current_reason = data.get('reason', '')
                st.session_state.current_type = data.get('type', '')
                
                return format_recommendations(lang)
                
            except Exception as e:
                last_error = str(e)
                # 할당량 초과 에러인 경우에만 다음 조합 시도
                if any(x in last_error for x in ["ResourceExhausted", "429", "quota", "Quota"]):
                    continue 
                else:
                    return f"⚠️ **기술적 에러 발생 ({model_name}):** {last_error}"
                    
    return "⚠️ **모든 방어막(API 키 및 모델)이 한도를 초과했습니다.**\n\n현재 동시 사용자가 너무 많습니다. 약 1분만 기다려 주시면 한도가 초기화됩니다."

def format_recommendations(lang):
    recs = st.session_state.current_recommendations
    start_idx = st.session_state.current_page * 3
    end_idx = start_idx + 3
    current_recs = recs[start_idx:end_idx]
    
    if not current_recs:
        return "더 이상 추천할 문서가 없습니다."

    output = f"### [분류 근거]\n{st.session_state.current_reason}\n\n"
    output += f"**분류**\nDoc Type: {st.session_state.current_type}\nCategory: {st.session_state.current_classification}\n\n"
    output += "### 확인할 문서 (가중치 순 추천)\n"
    
    for i, r in enumerate(current_recs):
        rank = start_idx + i + 1
        output += f"**{rank}순위: {r['no']} / {r['fix']} / {r['instrument']}**\n"
        output += f"- 설명: {r['reasoning']} (가중치: {r['weight']}점)\n\n"
        
        # 링크 추가
        key = (r['instrument'].upper(), r['no'].split('_')[-1].split('-')[-1], lang) # 번호만 추출 시도
        # 더 정확한 매칭을 위해 원본 번호로도 시도
        match = re.search(r'\d{3}', r['no'])
        if match:
            num_only = match.group()
            key = (r['instrument'].upper(), num_only, lang)
            if key in DOCUMENT_LINKS:
                url = DOCUMENT_LINKS[key]
                label = f"{r['no']} 문서 바로가기" if lang == "KR" else f"Direct Link: {r['no']}"
                output += f"🔗 [{label}]({url})\n\n"

    if len(recs) > end_idx:
        output += "---\n💡 **해당 문서로 해결방법을 찾지 못했다면?**\n"
        # 버튼 처리는 아래 UI 쪽에서 수행
    else:
        output += "\n\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함(폴더)**](https://works.do/FYhb6GY)" if lang=="KR" else "\n\n---\n💡 [**Check Entire Folder**](https://works.do/FYhb6GY)"
    
    return output

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
    .stButton>button { border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-container">
    <div style="font-size: 2.2rem; font-weight: 700;">MS·TS guide chatbot</div>
    <div style="opacity: 0.9;">문제 증상을 입력하면 지침서 번호를 알려드립니다.</div>
</div>
""", unsafe_allow_html=True)

if "messages" not in st.session_state: st.session_state.messages = []
if "vector_db" not in st.session_state:
    with st.spinner("AI가 지침서 데이터베이스를 최적화하고 있습니다... (처음 1회만 소요)"):
        st.session_state.vector_db = get_vector_db()
if "current_recommendations" not in st.session_state: st.session_state.current_recommendations = []

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# 다음 가중치 버튼 처리
if st.session_state.current_recommendations and (st.session_state.current_page + 1) * 3 < len(st.session_state.current_recommendations):
    if st.button("🔽 해당 문서로 해결방법을 찾지 못했다면? 다음 가중치 문서 보기", use_container_width=True):
        st.session_state.current_page += 1
        lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in st.session_state.messages[-1]["content"]) else "EN"
        res = format_recommendations(lang)
        with st.chat_message("assistant", avatar="🐻"):
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
        st.rerun()

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
    st.rerun()
