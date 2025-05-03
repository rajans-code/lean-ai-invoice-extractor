# Lean-AI Invoice Extractor

**Lean-AI Invoice Extractor** is an intelligent document processing tool designed for automated extraction of key invoice fields using locally hosted [IBM Granite LLM](https://github.com/ibm-granite)) LLMs via Ollama (https://ollama.com/) and structured document parsing with [Docling](https://docling.io/). It supports processing of PDF, DOCX, DOC, XLSX, and image-based invoices.

**💻 Designed for Local Use**  
Everything can run on a regular laptop or desktop PC and no GPU or cloud infrastructure required. 

---

## 🔍 Features

- Extracts key invoice fields:
  - Customer Name
  - Invoice Number
  - Invoice Date
  - Invoice Amount
- Supports multiple input formats using Docling https://github.com/docling-project:
  - `.pdf`, `.docx`, `.xlsx`, and image files (`.png`, `.jpg`, `.tiff`, `.bmp`)
- Fully offline & secure using [IBM Granite LLM](https://github.com/ibm-granite)
- Generates batch-wise structured JSON and a CSV summary
- Logging and traceability for auditing

---

## 🧠 Granite LLM Usage

This project **explicitly uses IBM's open-source Granite LLM** (`granite3.3:2b`) via the [Ollama](https://ollama.com) runtime.

### Setup

ollama pull granite3.3:2b
ollama run granite3.3:2b


Ensure Ollama server is running on:


OLLAMA_ENDPOINT=http://localhost:11434/api/generate


---

## 🛠️ Installation


git clone https://github.com/yourusername/lean-ai-invoice-extractor.git
cd lean-ai-invoice-extractor
python -m venv venv
venv\Scripts\activate      # On Windows
pip install -r requirements.txt


---

## ⚙️ Configuration

Create a `.env` file in the root:


INPUT_DIR=C:\Invoice\Input
BASE_OUTPUT_DIR=C:\Invoice\Output
OLLAMA_MODEL=granite3.3:2b
OLLAMA_ENDPOINT=http://localhost:11434/api/generate
DEBUG_TRACE=False


---

## 🚀 Usage

Place your invoice files in the input folder and run:


python lean_ai_invoice_extractor.py


Output will be organized in a timestamped batch folder under `Output/`, including:

- `.full.json`: extracted content
- `.filtered.json`: LLM response
- `summary.csv`: consolidated data
- `log/batch_<timestamp>.log`: trace log

---
