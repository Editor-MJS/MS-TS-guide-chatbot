import pandas as pd
import os

csv_path = 'c:/Users/mih97/Desktop/대웅제약 인턴/Step 6 Ms_TS 과제/document_links.csv'
xlsx_path = 'c:/Users/mih97/Desktop/대웅제약 인턴/Step 6 Ms_TS 과제/document_links.xlsx'

if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    df.to_excel(xlsx_path, index=False)
    print(f"Successfully converted {csv_path} to {xlsx_path}")
else:
    print(f"CSV file not found at {csv_path}")
