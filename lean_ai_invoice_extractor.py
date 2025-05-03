import os
import json
import requests
import traceback
import re
import csv
import pandas as pd
from pathlib import Path
from datetime import datetime
from io import StringIO

from docling_parse.pdf_parser import DoclingPdfParser
from docling_core.types.doc.page import TextCellUnit
from docling.document_converter import DocumentConverter
from PIL import Image, ImageEnhance
import pytesseract

# === Configuration ===
INPUT_DIR = r"C:\Docling_working_dir\Input"
BASE_OUTPUT_DIR = r"C:\Docling_working_dir\Output"
BATCH_ID = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]
OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, BATCH_ID)
LOG_DIR = os.path.join(OUTPUT_DIR, "log")
LOG_PATH = os.path.join(LOG_DIR, f"batch_{BATCH_ID}.log")
OLLAMA_MODEL = "granite3.3:2b"
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
DEBUG_TRACE = False

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

def log(message):
    print(message)
    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        log_file.write(message + "\n")

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_text_lines(full_json):
    text_data = []
    pages = full_json.get("pages", {})

    def safe_int(k):
        try:
            return int(k)
        except:
            return 0

    for page_key in sorted(pages.keys(), key=safe_int):
        page = pages[page_key]
        lines = []

        blocks = page.get("text_blocks", [])
        if blocks:
            for block in blocks:
                if isinstance(block, dict):
                    text = block.get("text", "")
                    if text:
                        cleaned = text.strip()
                        if cleaned and not re.fullmatch(r"[\-\s]*", cleaned):
                            lines.append(cleaned)

        elif "paragraphs" in page:
            for p in page["paragraphs"]:
                if isinstance(p, str):
                    cleaned = p.strip()
                    if cleaned and not re.fullmatch(r"[\-\s]*", cleaned):
                        lines.append(cleaned)

        elif "text" in page and isinstance(page["text"], str):
            for line in page["text"].splitlines():
                cleaned = line.strip()
                if cleaned and not re.fullmatch(r"[\-\s]*", cleaned):
                    lines.append(cleaned)

        if lines:
            text_data.append({
                "page_number": page_key,
                "text_lines": lines
            })

    return text_data

def preprocess_image(image):
    base_width = 1200
    w_percent = (base_width / float(image.size[0]))
    h_size = int((float(image.size[1]) * float(w_percent)))
    image = image.resize((base_width, h_size), Image.LANCZOS)
    enhancer = ImageEnhance.Sharpness(image)
    return enhancer.enhance(2.0)

def extract_text_from_image(image_path):
    image = Image.open(image_path).convert("RGB")
    image = preprocess_image(image)
    text = pytesseract.image_to_string(image)
    if not text.strip():
        return []
    text_lines = [line.strip() for line in text.split("\n") if line.strip()]
    return [{"page_number": 1, "text_lines": text_lines}]

def send_to_ollama_from_fulljson(full_json_path, filtered_json_path):
    with open(full_json_path, "r", encoding="utf-8") as f:
        full_json = json.load(f)

    invoice_text_data = extract_text_lines(full_json)
    all_lines = []
    for page in invoice_text_data:
        all_lines.extend(page.get("text_lines", []))
    invoice_text = "\n".join(all_lines)

    prompt = f"""
You are an intelligent assistant for invoice information extraction.

Given the following invoice text, extract the following fields and return a JSON with these keys:
- "customer_name"
- "invoice_number"
- "invoice_date"
- "invoice_amount"

If any field is missing, set its value to null.

Here is the invoice text:
{invoice_text}

Return ONLY the JSON object.
"""

    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    try:
        response = requests.post(OLLAMA_ENDPOINT, json=payload)
        response.raise_for_status()
        result = response.json()
        output = result.get("response", "").strip()

        log("LLM's Response:")
        log(output)

        with open(filtered_json_path, "w", encoding="utf-8") as f:
            f.write(output)

    except Exception as e:
        log(f"[Ollama ❌] Error: {e}")

def parse_pdf_to_dict(input_path):
    parser = DoclingPdfParser()
    doc = parser.load(path_or_stream=input_path)
    pages = {}
    for idx, page in doc.iterate_pages():
        lines = [cell.text.strip() for cell in page.iterate_cells(TextCellUnit.LINE) if cell.text.strip()]
        pages[str(idx + 1)] = {"text_blocks": [{"text": line} for line in lines]}
    return {"pages": pages, "invoice_images": []}

def parse_docx_to_modeldump(input_path):
    converter = DocumentConverter()
    result = converter.convert(input_path)
    full = result.document.model_dump(mode="json")
    lines = []
    for text_entry in full.get("texts", []):
        content = text_entry.get("text", "").strip()
        if content and not re.fullmatch(r"[\-\s]*", content):
            lines.append({"text": content})
    pages = {}
    if lines:
        pages["1"] = {"text_blocks": lines}
    return {"pages": pages, "invoice_images": []}

def parse_xlsx_invoice(filepath):
    df = pd.read_excel(filepath)
    lines = []
    for _, row in df.iterrows():
        row_text = ", ".join(str(v) for v in row if pd.notna(v))
        if row_text.strip():
            lines.append({"text": row_text.strip()})
    return {
        "pages": {
            "1": {"text_blocks": lines}
        },
        "invoice_images": [str(filepath)]
    }

def parse_csv_invoice(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        all_lines = f.readlines()
    table_start_idx = -1
    for idx, line in enumerate(all_lines):
        if line.strip().lower().startswith("description"):
            table_start_idx = idx
            break
    if table_start_idx == -1:
        raise ValueError("Could not locate the table header in CSV.")
    tabular_text = "".join(all_lines[table_start_idx:])
    df = pd.read_csv(StringIO(tabular_text))
    lines = []
    for _, row in df.iterrows():
        row_text = ", ".join(str(v) for v in row if pd.notna(v))
        if row_text.strip():
            lines.append({"text": row_text.strip()})
    return {
        "pages": {
            "1": {"text_blocks": lines}
        },
        "invoice_images": [str(filepath)]
    }

def generate_summary_csv(output_dir):
    summary_path = os.path.join(output_dir, "summary.csv")
    records = []
    for file in os.listdir(output_dir):
        if file.endswith(".filtered.json"):
            file_path = os.path.join(output_dir, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    record = {
                        "batch_id": BATCH_ID,
                        "filename": file.replace(".filtered.json", ""),
                        "customer_name": data.get("customer_name", ""),
                        "invoice_number": data.get("invoice_number", ""),
                        "invoice_date": data.get("invoice_date", ""),
                        "invoice_amount": data.get("invoice_amount", "")
                    }
                    records.append(record)
            except Exception as e:
                log(f"[WARN] Skipping {file}: {e}")

    if records:
        with open(summary_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
            writer.writerow(["batch_id", "filename", "customer_name", "invoice_number", "invoice_date", "invoice_amount"])
            for r in records:
                writer.writerow([
                    r["batch_id"],
                    r["filename"],
                    r["customer_name"],
                    r["invoice_number"],
                    r["invoice_date"],
                    r["invoice_amount"]
                ])
        log(f"[INFO] Summary CSV created at: {summary_path}")
    else:
        log("[INFO] No valid filtered.json files found to summarize.")

def main():
    log("[START] Invoice Batch Processor")
    for file_path in Path(INPUT_DIR).glob("*.*"):
        ext = file_path.suffix.lower()
        if ext not in {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".xlsx", ".csv"}:
            continue
        filename_stem = file_path.stem
        full_json_path = os.path.join(OUTPUT_DIR, f"{filename_stem}.full.json")
        filtered_json_path = os.path.join(OUTPUT_DIR, f"{filename_stem}.filtered.json")
        try:
            if ext == ".pdf":
                doc_data = parse_pdf_to_dict(str(file_path))
            elif ext in {".docx", ".doc"}:
                doc_data = parse_docx_to_modeldump(str(file_path))
            elif ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
                text_data = extract_text_from_image(str(file_path))
                doc_data = {"pages": {"1": {"text_blocks": [{"text": line} for line in text_data[0]["text_lines"]]}}, "invoice_images": [str(file_path)]}
            elif ext == ".xlsx":
                doc_data = parse_xlsx_invoice(str(file_path))
            elif ext == ".csv":
                doc_data = parse_csv_invoice(str(file_path))
            else:
                continue
            save_json(doc_data, full_json_path)
            send_to_ollama_from_fulljson(full_json_path, filtered_json_path)
            log(f"[DONE] {file_path.name}\n{'='*60}")
        except Exception as e:
            log(f"[❌ ERROR] Failed to process {file_path.name}: {e}")
            log(traceback.format_exc())
    generate_summary_csv(OUTPUT_DIR)
    log("[COMPLETE] All files processed.")

main()
