# -*- coding: utf-8 -*-
"""
==============================================================================
[대웅제약] 분석기기 자동화 시스템 v7.0 (Pure & Fast Translator)
==============================================================================
본 프로그램은 엑셀 파일을 읽어 표 형식과 레이아웃을 100% 보존하며 
초고속으로 한영 번역 PDF를 생성하는 자동화 도구입니다.
(비결정이자 대기 시간이 발생하는 AI 요약 기능을 제거하여 안정성을 높였습니다.)
==============================================================================
"""

import os
import sys
import glob
import re
import traceback
import warnings

# 라이브러리 경고 숨기기
warnings.filterwarnings("ignore")

# Windows Console Encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding="utf-8")

import win32com.client
from deep_translator import GoogleTranslator

# ──────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────
DIR_INPUT = "Input_Excel"
DIR_KOR = "Output_Kor"
DIR_EN = "Output_en"

# ──────────────────────────────────────────────────────────────
# [번역] 초고속 기계 번역 엔진
# ──────────────────────────────────────────────────────────────
def translate_text(text):
    if not text or not str(text).strip(): return text
    if not re.search('[가-힣]', str(text)): return text # 한글 없으면 패스
    try:
        return GoogleTranslator(source='ko', target='en').translate(text)
    except:
        return text

# ──────────────────────────────────────────────────────────────
# [핵심] 엑셀 직접 번역 및 PDF 변환 엔진
# ──────────────────────────────────────────────────────────────
def process_excel_automation(input_path, doc_id):
    excel = None
    wb = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        
        abs_input = os.path.abspath(input_path)
        wb = excel.Workbooks.Open(abs_input)
        
        # --- [1단계] 한글 PDF 저장 (가로 비율 최적화) ---
        kor_pdf_path = os.path.abspath(os.path.join(DIR_KOR, f"{doc_id}.pdf"))
        for sh in wb.Sheets:
            sh.PageSetup.Orientation = 2 # Landscape
            sh.PageSetup.FitToPagesWide = 1
            sh.PageSetup.FitToPagesTall = False

        wb.ExportAsFixedFormat(0, kor_pdf_path)
        print(f"  - STEP 1: Korean PDF saved.")

        # --- [2단계] 셀 텍스트 직접 번역 ---
        print(f"  - STEP 2: Translating cells...", end="", flush=True)
        for sh in wb.Sheets:
            used = sh.UsedRange
            if not used: continue
            for cell in used:
                if cell.Value and isinstance(cell.Value, str):
                    cell.Value = translate_text(cell.Value)
        print(" Done")

        # --- [3단계] 영어 PDF 저장 (레이아웃 보존) ---
        en_pdf_path = os.path.abspath(os.path.join(DIR_EN, f"{doc_id} en.pdf"))
        wb.ExportAsFixedFormat(0, en_pdf_path)
        print(f"  - STEP 3: English PDF saved.")
        
        return True

    except Exception as e:
        print(f"    [Error] Processing fail: {e}")
        return False
    finally:
        if wb: wb.Close(False)
        if excel: excel.Quit()

# ──────────────────────────────────────────────────────────────
# 메인 엔진
# ──────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print("  Daewoong QC Automation System v7.0 (Pure Translation)")
    print(f"{'='*60}")

    # 폴더 준비
    for d in [DIR_INPUT, DIR_KOR, DIR_EN]:
        os.makedirs(d, exist_ok=True)

    excel_files = sorted(glob.glob(os.path.join(DIR_INPUT, "*.xlsx")))
    excel_files = [f for f in excel_files if not os.path.basename(f).startswith("~$")]

    if not excel_files:
        print(f"\n[Empty] Please put original files in '{DIR_INPUT}' folder.")
        return

    print(f"\n[Process Target: {len(excel_files)} file(s)]")
    
    for f in excel_files:
        fname = os.path.basename(f)
        match = re.search(r'([A-Za-z]+[-_\s]?\d+)', fname)
        doc_id = match.group(1).replace(" ", "_").upper() if match else fname.split(".")[0]
        
        print(f"\n▶ [{doc_id}] Processing...")
        success = process_excel_automation(f, doc_id)
        
        if success:
            print(f"  ✅ SUCCESS: {doc_id} work finished.")
        else:
            print(f"  ❌ FAILED: {doc_id}")

    print(f"\n{'='*60}")
    print("  All operations finished. Thank you.")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
