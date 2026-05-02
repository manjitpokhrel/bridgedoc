## ⚡ Quick Start

### 1. Clone
git clone https://github.com/manjitpokhrel/bridgedoc.git
cd bridgedoc

### 2. Install
pip install -r backend/requirements.txt

### 3. Run
cd backend
uvicorn main:app --port 8000

### 4. Open
Open index.html in your browser

### 5. Use
- Enter your TMT API key
- Select translation direction
- Upload your file (PDF, DOCX, CSV, TSV)
- Click Translate
- Download result


# 🌉 BridgeDoc
### Trilingual Document Translation System  
**Google TMT Hackathon 2026 — Track 2**  
**Team: Exponent**

---

## 🚀 What is BridgeDoc?
BridgeDoc is a **layout-aware, multi-format document translation system** that translates files across:

-  English  
-  Nepali  
-  Tamang  

Unlike typical translators, BridgeDoc **preserves structure, formatting, and readability**, making it usable for real-world documents—not just raw text.

---

## 🏆 Why It Matters
Most translation tools:
- ❌ Break PDF layouts  
- ❌ Ignore tables  
- ❌ Corrupt structured files  

BridgeDoc solves this with:
- ✅ Layout-aware reconstruction  
- ✅ Format-specific processing pipelines  
- ✅ Intelligent content filtering  
- ✅ Quality verification system  

---

## 🎬 Demo
▶️ https://www.youtube.com/watch?v=jDM91IAJLR4

---

## ⚡ Core Features

### 📄 Multi-Format Support
| Format | Capability |
|------|--------|
| PDF | Layout reconstruction + table detection |
| DOCX | Full structure preservation |
| CSV/TSV | Smart column-aware translation |

---

### 🌐 All 6 Translation Directions
- English ↔ Nepali  
- English ↔ Tamang  
- Nepali ↔ Tamang  

---

### 🧠 Layout Preservation Engine (PDF)
- Positional text extraction (bounding boxes)  
- Reading order reconstruction  
- Table row + column detection  
- Adaptive paragraph expansion  
- Font scaling fallback  
- Redaction-based text replacement (no ghost layer)  
- Embedded **Noto Sans Devanagari**

---

### 📝 DOCX Intelligence
- Preserves:
  - Paragraphs  
  - Tables  
  - Headers / Footers  
  - Inline formatting  
- Sentence-level translation pipeline

---

### 📊 Smart CSV Handling
Automatically skips:
- Numbers  
- Dates  
- Emails  
- URLs  
- Phone numbers  

→ Only meaningful text is translated.

---

### 🔍 Quality Verification (Optional)
- Back-translation audit  
- Sentence-level confidence scoring  
- Low-confidence flagging  
- UI-based quality score  

---

### 🛡️ Robustness
- Detects scanned PDFs  
- Rejects empty files  
- Handles malformed CSV rows  
- API retries with exponential backoff  
- Safe fallback to original text  

---

## 🏗️ Architecture

```
Frontend (HTML + CSS + JS)
        │
        ▼
FastAPI Backend
        │
        ├── File Validation
        ├── Format-Specific Extraction
        ├── Sentence Segmentation
        ├── Async TMT API Calls
        ├── Quality Verification
        └── Layout-Aware Reconstruction
```

---

## 📁 Project Structure

```
bridgedoc/
├── index.html
├── styles.css
├── app.js
├── backend/
│   ├── main.py
│   ├── core/
│   ├── processors/
│   └── utils/
├── fonts/
└── samples/
```

---

## ⚙️ Quick Start

### 1. Clone
```bash
git clone https://github.com/manjitpokhrel/bridgedoc
cd bridgedoc
```

### 2. Setup Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install
```bash
pip install -r backend/requirements.txt
```

### 4. Configure API
Create `backend/.env`:
```
TMT_API_KEY=your_team_token_here
TMT_BASE_URL=https://tmt.ilprl.ku.edu.np
```

### 5. Run Backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 6. Launch Frontend
Open `index.html`

---

## 🧠 Technical Highlights
- Custom trilingual sentence segmenter  
- Devanagari dialogue detection  
- PDF table structure reconstruction  
- Adaptive layout expansion engine  
- Async concurrency with semaphore control  
- Deduplicated translation memory  
- Structured task polling  

---

## ⚠️ Limitations
- No OCR (scanned PDFs unsupported)  
- Complex PDFs may have minor layout shifts  
- Long translations may affect spacing  
- Text inside images not translated  

---

## 🔮 Future Improvements
- OCR integration (for scanned PDFs)  
- More low-resource language support  
- Better layout ML models  
- Real-time collaboration  

---

## 📜 License
MIT License

---

## 🏁 Hackathon Submission
- **Event:** Google TMT Hackathon 2026  
- **Track:** File Translation Tool (Track 2)  
- **Team:** Exponent  

---

## ⭐ If You Like This Project
Give it a star ⭐ — it helps visibility and future development!
