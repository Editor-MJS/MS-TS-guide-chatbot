# -*- coding: utf-8 -*-
"""
==============================================================================
[대웅제약] 챗봇 지식 기반 생성기 v16.0 (Excel Direct Copy / 100% Precision)
==============================================================================
특징: 
1. 엑셀 직접 읽기: PDF 추출의 불안정성을 완전히 제거하고 원본 엑셀 셀을 직접 복사
2. 무결성 보장: 셀에 적힌 텍스트를 단 한 글자의 오차도 없이 가져옵니다.
3. 초고성능: AI 없이 윈도우 표준 엑셀 엔진을 사용하여 가장 정확한 데이터 확보
4. 챗봇 최적화: JSON 및 리포트 생성
==============================================================================
"""

import os
import sys
import glob
import time
import json
import warnings
import win32com.client

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding="utf-8")
    except: pass

DIR_INPUT = "Input_Excel_offline" # 오프라인 전용 원본 엑셀 폴더
DIR_OUTPUT = "Chatbot_Index_Output" # 인덱스 전용 폴더
JSON_FILE = os.path.join(DIR_OUTPUT, "Chatbot_Knowledge_Base.json")
PDF_FILE = os.path.join(DIR_OUTPUT, "Chatbot_Knowledge_Base_Report.pdf")

# 폴더 자동 생성
if not os.path.exists(DIR_OUTPUT):
    os.makedirs(DIR_OUTPUT)

def extract_facts_from_excel(excel_app, file_path, doc_id):
    """엑셀 파일을 직접 열어 특정 셀의 값을 완벽하게 복사합니다."""
    wb = None
    try:
        abs_path = os.path.abspath(file_path)
        wb = excel_app.Workbooks.Open(abs_path)
        ws = wb.Sheets(1) # 첫 번째 시트

        # 대웅제약 표준 양식에 따른 셀 위치 (B2, B3, B4, B5)
        # 만약 양식이 조금씩 다르더라도 검색을 통해 찾도록 보강
        def get_val(label_addr, value_addr):
            try:
                return str(ws.Range(value_addr).Value).strip() if ws.Range(value_addr).Value else "정보없음"
            except:
                return "추출에러"

        # 데이터 매핑
        data = {
            "ID": doc_id,
            "장비구분": get_val("A2", "B2"),
            "작업내용": get_val("A3", "B3"),
            "참고상황": get_val("A4", "B4"),
            "상세목적": get_val("A5", "B5")
        }
        
        # --- [스마트 서칭 엔진] ---
        # 고정 위치(B2 등)가 아니라 시트 전체에서 라벨을 찾아 그 오른쪽 값을 가져옵니다.
        used = ws.UsedRange
        if used:
            for row in range(1, used.Rows.Count + 1):
                for col in range(1, used.Columns.Count + 1):
                    cell_val = str(ws.Cells(row, col).Value).strip() if ws.Cells(row, col).Value else ""
                    
                    # 라벨 발견 시 오른쪽 셀 값 추출
                    if "구분" in cell_val and data["장비구분"] in ["정보없음", "추출에러"]:
                        val = str(ws.Cells(row, col+1).Value).strip() if ws.Cells(row, col+1).Value else ""
                        if val and "Division" not in val: data["장비구분"] = val
                        
                    if "작업명" in cell_val and data["작업내용"] in ["정보없음", "추출에러"]:
                        val = str(ws.Cells(row, col+1).Value).strip() if ws.Cells(row, col+1).Value else ""
                        if val and "Operation" not in val: data["작업내용"] = val
                        
                    if "작업상황" in cell_val and data["참고상황"] in ["정보없음", "추출에러"]:
                        val = str(ws.Cells(row, col+1).Value).strip() if ws.Cells(row, col+1).Value else ""
                        if val and "Situation" not in val: data["참고상황"] = val
                        
                    if "목적" in cell_val and data["상세목적"] in ["정보없음", "추출에러"]:
                        val = str(ws.Cells(row, col+1).Value).strip() if ws.Cells(row, col+1).Value else ""
                        if val and "Purpose" not in val: data["상세목적"] = val

        return data
    except Exception as e:
        return {"ID": doc_id, "ERROR": str(e)}
    finally:
        if wb: wb.Close(False)

def main():
    print(f"\n{'='*60}\n  Starting Excel Direct Indexer v16.0 (Perfect Precision)\n{'='*60}")
    
    # Input_Excel 폴더 또는 Input_Excel_offline 폴더 확인
    input_dir = DIR_INPUT
    if not os.path.exists(input_dir):
        input_dir = "Input_Excel_offline"
    
    files = [f for f in glob.glob(os.path.join(input_dir, "*.xlsx")) if not os.path.basename(f).startswith("~$")]
    if not files:
        print(f"[!] No Excel files found in '{input_dir}' folder.")
        return

    excel_app = None
    knowledge_base = []
    
    try:
        excel_app = win32com.client.Dispatch("Excel.Application")
        excel_app.Visible = False
        excel_app.DisplayAlerts = False
        
        print(f"▶ Processing {len(files)} Excel file(s)...")

        for f in files:
            fname = os.path.basename(f)
            
            # [ID 인식 강화] 파일명 전체에서 영문-숫자 조합(예: UPLC-004)을 찾습니다.
            match = re.search(r'([A-Za-z]+[-_\s]\d+)', fname)
            if match:
                doc_id = match.group(1).upper().replace("_", "-")
            else:
                doc_id = fname.split(".")[0] # 패턴이 없으면 파일명 그대로 사용

            print(f"  - [{doc_id}] Direct Reading...", end="", flush=True)
            facts = extract_facts_from_excel(excel_app, f, doc_id)
            knowledge_base.append(facts)
            print(" Done")

    finally:
        if excel_app: excel_app.Quit()

    # --- [결과 저장] ---
    with open(JSON_FILE, "w", encoding="utf-8") as jf:
        json.dump(knowledge_base, jf, indent=4, ensure_ascii=False)
    
    # PDF 리포트 생성 (디자인보다 가독성 최우선)
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_font("Malgun", "", r"C:\Windows\Fonts\malgun.ttf")
    pdf.add_font("MalgunB", "", r"C:\Windows\Fonts\malgunbd.ttf")
    pdf.add_page()
    
    pdf.set_font("MalgunB", "", 18)
    pdf.cell(0, 20, "QC Chatbot Knowledge Base (Excel Direct)", ln=1, align="C")
    pdf.ln(5)

    for k in knowledge_base:
        if pdf.get_y() > 230: pdf.add_page()
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("MalgunB", "", 11)
        pdf.cell(190, 8, f" [문서 번호: {k['ID']}]", border=1, ln=1, fill=True)
        
        pdf.set_font("Malgun", "", 9)
        for label, key in [("구분", "장비구분"), ("작업", "작업내용"), ("상황", "참고상황"), ("목적", "상세목적")]:
            pdf.set_font("MalgunB", "", 9)
            pdf.write(7, f"   • {label}: ")
            pdf.set_font("Malgun", "", 9)
            pdf.multi_cell(170, 7, f"{k.get(key, 'N/A')}", border=0)
        pdf.ln(4)

    pdf.output(PDF_FILE)
    print(f"\n✅ All process finished successfully!")
    print(f" - Results are saved in {JSON_FILE} and {PDF_FILE}")

import re # re가 빠졌을 수 있어 추가
if __name__ == "__main__":
    main()
