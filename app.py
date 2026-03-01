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
제시된 [RETRIEVED DATA]는 사용자의 질문과 의미상 가장 유사한 문서들입니다.

[중요 규칙]
1. 장비 매칭: 사용자의 질문에 특정 장비(UPLC 또는 HPLC)가 언급되었다면, 반드시 해당 장비의 문서를 최우선적으로 추천하십시오.
2. 상세 분류: 질문을 분석하여 '트러블슈팅' 같은 넓은 범위가 아니라, '**RT 지연 현상**', '**피크 모양 이상**', '**압력 상승**' 등 구체적인 원인이나 현상 위주로 분류명을 생성하십시오.
3. 추천 로직: 'Weight(절대 가중치)'가 높은 순서대로 답변을 구성하되, 장비 호환성을 최우선으로 합니다.
4. 말투: 전문가답고 정중하게 답변하십시오.

[출력 형식 (JSON)]
반드시 다음 구조의 JSON 형식으로만 답변하세요:
{
  "classification": "상세 현상/원인 분류명 (예: RT 지연 현상)",
  "reason": "분류 근거 설명 (짧고 명확하게)",
  "recommendations": [
    {"no": "문서번호", "fix": "해결방법 요약", "instrument": "장비명", "reasoning": "설명/근거", "weight": 점수},
    ... 관련 있는 문서들(최대 5개) ...
  ]
}
"""

def get_gemini_response(user_prompt):
    lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in user_prompt) else "EN"
    
    if st.session_state.vector_db is None:
        return "⚠️ 데이터베이스가 초기화되지 않았습니다. 관리자에게 문의하세요."
        
    prompt_lower = user_prompt.lower()
    instrument_filter = None
    if "uplc" in prompt_lower:
        instrument_filter = "UPLC"
    elif "hplc" in prompt_lower:
        instrument_filter = "HPLC"
        
    raw_docs = st.session_state.vector_db.similarity_search(user_prompt, k=15)
    
    if instrument_filter:
        retrieved_docs = [d for d in raw_docs if d.metadata.get('instrument') == instrument_filter]
        if len(retrieved_docs) < 5:
            others = [d for d in raw_docs if d.metadata.get('instrument') != instrument_filter]
            retrieved_docs.extend(others[:5-len(retrieved_docs)])
    else:
        retrieved_docs = raw_docs[:8]
    
    retrieved_context = "## [RETRIEVED DATA]\n"
    for d in retrieved_docs:
        m = d.metadata
        retrieved_context += f"- DocNo: {m.get('doc_no')} | Fix: {m.get('fix')} | Symptom: {m.get('symptom')} | InternalRank: {m.get('rank')} | Weight: {m.get('weight')} | Reasoning: {m.get('reasoning')} | Instrument: {m.get('instrument')}\n"
    
    full_prompt = f"{SYSTEM_PROMPT}\n{retrieved_context}\n\n[USER QUESTION]\n{user_prompt}"
    
    models_to_try = [
        "gemini-2.5-flash-lite", 
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash", 
        "gemini-1.5-flash", 
        "gemini-1.5-flash-8b"
    ]
    
    current_keys = API_KEYS.copy()
    random.shuffle(current_keys)
    
    last_error = ""
    
    for api_key in current_keys:
        genai.configure(api_key=api_key)
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(full_prompt, generation_config={"response_mime_type": "application/json"})
                
                resp_json = response.text
                if resp_json.startswith("```json"):
                    resp_json = resp_json.replace("```json", "").replace("```", "").strip()
                
                data = json.loads(resp_json)
                
                st.session_state.current_recommendations = data.get('recommendations', [])
                st.session_state.current_page = 0
                st.session_state.current_classification = data.get('classification', '')
                st.session_state.current_reason = data.get('reason', '')
                
                return format_recommendations(lang)
                
            except Exception as e:
                last_error = str(e)
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

    if lang == "KR":
        output = f"🐻\n[분류 근거] {st.session_state.current_reason}\n\n"
        output += f"사용자의 질문에 따라 분석결과 **{st.session_state.current_classification}**으로 분류되었습니다.\n이러한 유형에 따라 다음과 같은 문서들을 추천합니다.\n\n"
    else:
        output = f"🐻\n[Logic] {st.session_state.current_reason}\n\n"
        output += f"Based on your question, it has been classified as **{st.session_state.current_classification}**.\nWe recommend the following documents:\n\n"
    
    for i, r in enumerate(current_recs):
        rank = start_idx + i + 1
        output += f"**{rank}순위: {r['no']} / {r['fix']} / {r['instrument']}**\n"
        output += f"설명: {r['reasoning']} (가중치: {r['weight']}점)\n\n" # 줄바꿈 추가
        
        instr = str(r.get('instrument', '')).upper()
        doc_no = str(r.get('no', ''))
        
        match = re.search(r'\d+', doc_no)
        if match:
            num = match.group().lstrip('0')
            if not num: num = "0"
            
            target_instr = "HPLC" if "HPLC" in instr else "UPLC"
            key = (target_instr, num, lang)
            
            if key in DOCUMENT_LINKS:
                url = DOCUMENT_LINKS[key]
                label = "📄 문서 바로가기" if lang == "KR" else "📄 View Document"
                output += f"🔗 [{label}]({url})\n\n"
        
        # 순위 간 구분선 (선택 사항)
        if i < len(current_recs) - 1:
            output += "---\n\n"
    
    # Footer 처리
    if len(recs) <= end_idx:
        global_link = "https://works.do/FV0WJOQ"
        if lang == "KR":
            output += f"\n---\n💡 찾으시는 문서가 없나요? [**전체 문서함(폴더)**]({global_link})"
        else:
            output += f"\n---\n💡 Haven't found what you're looking for? [**Check Entire Folder**]({global_link})"
    
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
    with st.spinner("AI가 지침서 데이터베이스를 최적화하고 있습니다..."):
        st.session_state.vector_db = get_vector_db()
if "current_recommendations" not in st.session_state: st.session_state.current_recommendations = []
if "current_page" not in st.session_state: st.session_state.current_page = 0

for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🐻" if m["role"]=="assistant" else "🧑‍💻"):
        st.markdown(m["content"])

# 다음 가중치 버튼 (유저 요청: "찾으시는 해결방법이 아닙니까?" 문구 적용)
if st.session_state.current_recommendations and (st.session_state.current_page + 1) * 3 < len(st.session_state.current_recommendations):
    if st.button("🤔 찾으시는 해결방법이 아닙니까? (다른 가중치 문서 보기)", use_container_width=True):
        st.session_state.current_page += 1
        last_user_msg = ""
        for m in reversed(st.session_state.messages):
            if m["role"] == "user":
                last_user_msg = m["content"]
                break
        lang = "KR" if any(0xAC00 <= ord(c) <= 0xD7A3 for c in last_user_msg) else "EN"
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
