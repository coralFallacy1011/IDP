# LexAI — Intelligent Legal Document Processing Platform

LexAI is a full-stack AI platform built to automate the lifecycle of legal document management. It combines OCR, NLP, semantic search, RAG-based chat, document generation, blockchain immutability, and biometric authentication into a single cohesive system.

---

## Table of Contents

- [Project Overview](#project-overview)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Blockchain Setup](#blockchain-setup)
  - [Frontend Setup](#frontend-setup)
  - [Quick Start (Windows)](#quick-start-windows)
- [API Reference](#api-reference)
- [Authentication & Security](#authentication--security)
- [Blockchain Integration](#blockchain-integration)
- [Hardware (ESP32 Fingerprint)](#hardware-esp32-fingerprint)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
- [Module Status](#module-status)

---

## Project Overview

LexAI was built as an Intelligent Document Processing (IDP) system focused on the legal domain — specifically Indian legal documents such as FIRs, contracts, affidavits, rental agreements, power-of-attorney, and court judgments.

The problem it solves: legal professionals spend enormous time manually reading, classifying, extracting data from, and verifying documents. LexAI automates all of this while adding an immutable audit trail via blockchain and securing access with biometric (fingerprint + face) authentication.

The system is designed around three layers:

1. **AI Pipeline** — OCR → Classification → Entity Extraction → Summarization → Risk Analysis → Embedding → RAG
2. **Security Layer** — ESP32 fingerprint sensor + face recognition + JWT-based auth + audit logging
3. **Blockchain Layer** — Every document is SHA-256 hashed and registered on a local Ethereum chain (Hardhat), enabling tamper detection

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LexAI Platform                           │
└─────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐       ┌──────────────────────────────────┐
  │  Next.js 15     │ HTTP  │     Flask Backend  :5000         │
  │  Frontend       │◄─────►│                                  │
  │  (TypeScript)   │       │  /api/ocr/         OCR pipeline  │
  └─────────────────┘       │  /api/ai/          RAG + NLP     │
                            │  /api/documents/   CRUD          │
  ┌─────────────────┐       │  /api/blockchain/  Chain ops     │
  │  ESP32 +        │ POST  │  /api/biometric/   Fingerprint   │
  │  Fingerprint    │──────►│  /api/face/        Face recog.   │
  │  Sensor         │       │  /verify           Root verify   │
  └─────────────────┘       └──────────────┬───────────────────┘
                                           │
                      ┌────────────────────┼────────────────────┐
                      │                    │                     │
              ┌───────▼──────┐   ┌─────────▼──────┐   ┌────────▼───────┐
              │  MongoDB     │   │  FAISS Index   │   │  Hardhat Node  │
              │  legal_idp   │   │  (embeddings)  │   │  :8545         │
              │  documents   │   │                │   │  Smart Contract│
              │  users       │   │                │   │  DocumentReg.  │
              │  audit_logs  │   │                │   │  .sol          │
              └──────────────┘   └────────────────┘   └────────────────┘
```

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| Web Framework | Flask + Flask-CORS |
| OCR Engine | Tesseract (pytesseract) + OpenCV preprocessing |
| Classification | HuggingFace Transformers (zero-shot / InLegalBERT) |
| NER / Entities | spaCy |
| Summarization | BART-large-CNN (HuggingFace pipeline) |
| Embeddings | sentence-transformers |
| Vector Store | FAISS (faiss-cpu) |
| RAG / Chat | LangChain + TinyLlama (ctransformers) |
| Document Templates | Jinja2 |
| PDF Export | ReportLab |
| Database | MongoDB (pymongo) |
| Blockchain Client | web3.py |
| Authentication | PyJWT |
| Face Recognition | dlib + custom face_recognition_service |

### Frontend
| Component | Technology |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS + shadcn/ui (Radix UI primitives) |
| State Management | Zustand |
| Forms | React Hook Form + Zod |
| Charts | Recharts |
| Animations | Framer Motion |
| HTTP Client | Axios |

### Blockchain
| Component | Technology |
|---|---|
| Local Chain | Hardhat (Ethereum) |
| Smart Contract | Solidity 0.8.20 |
| Contract | DocumentRegistry |
| Chain ID | 31337 (localhost) |
| RPC | http://127.0.0.1:8545 |

### Hardware
| Component | Details |
|---|---|
| Microcontroller | ESP32 |
| Biometric Sensor | Fingerprint sensor on UART2 (GPIO 16/17, 57600 baud) |
| Protocol | HTTP POST to Flask backend |

---

## Features

### OCR Processing
Upload a PDF, PNG, or JPG and get structured text output. The pipeline runs:
- Image preprocessing (deskew, denoise, normalize) via OpenCV
- Text extraction via Tesseract
- Token-level output with bounding boxes and confidence scores
- Results cached to `backend/preprocessed_cache/` to avoid re-processing

### AI Document Classification
Documents are automatically classified into types using a zero-shot HuggingFace transformer:
- FIR (First Information Report)
- Contract / Employment Agreement
- Affidavit
- Rental Agreement
- Power of Attorney
- Legal Notice
- Court Judgment

### Entity Extraction (NER)
spaCy-powered extraction of:
- Person names, organizations, locations
- Dates and monetary values
- IPC sections (Indian Penal Code references)
- Case numbers

### AI Summarization
Long legal documents are summarized using BART-large-CNN with a map-reduce strategy for multi-page documents.

### Risk Analysis
Automatically detects:
- Missing mandatory clauses
- Date inconsistencies
- Unusual or high-risk terms
- Compliance gaps

### Semantic Search
FAISS vector index built from sentence-transformer embeddings. Search across your entire document library by meaning, not just keywords.

### Legal Chatbot (RAG)
Ask questions about uploaded documents in natural language. The system retrieves relevant chunks from FAISS and feeds them as context to TinyLlama to generate grounded answers.

### Document Generation
Generate professional legal documents from Jinja2 templates with AI-filled fields:
- FIR
- Affidavit (general and specific)
- Rental Agreement
- Employment Contract
- Power of Attorney
- Legal Notice

Output as formatted PDF via ReportLab.

### Blockchain Registration & Verification
Every document processed through the OCR pipeline is:
1. SHA-256 hashed from the extracted text
2. Registered on the local Ethereum chain via `DocumentRegistry.sol`
3. Transaction hash stored in MongoDB alongside the document

To verify: recompute the hash from the stored OCR text and compare against the on-chain record. Tampering is detected immediately.

### Biometric Authentication
- **Fingerprint**: ESP32 reads the fingerprint sensor and POSTs the `fingerprint_id` to `/verify`. The backend looks up the user in MongoDB and returns a signed JWT.
- **Face Recognition**: Face enrollment and verification via `dlib` embeddings stored in the `face_embeddings` MongoDB collection.
- **JWT Auth**: All protected routes (`/api/blockchain/*`, `/api/documents/*`) require a valid `Authorization: Bearer <token>` header.

### Audit Logging
Every significant action (login, document upload, verification, view) is written to the `audit_logs` MongoDB collection with user, role, action, document ID, and timestamp.

---

## Project Structure

```
copy_idp/
├── IDP/                          # Main project directory
│   ├── backend/                  # Flask application
│   │   ├── app.py                # Entry point, blueprint registration, demo user seeding
│   │   ├── middleware/
│   │   │   └── auth.py           # JWT guard middleware
│   │   ├── models/
│   │   │   ├── document.py       # Domain models: Document, Page, Token, Block
│   │   │   └── nlp_models.py     # HuggingFace model wrappers (NER, classifier)
│   │   ├── routes/
│   │   │   ├── ai.py             # /api/ai/ — RAG query, NLP endpoints
│   │   │   ├── biometric.py      # /api/biometric/ — fingerprint auth
│   │   │   ├── blockchain.py     # /api/blockchain/ — register, verify, get
│   │   │   ├── documents.py      # /api/documents/ — upload, CRUD, generate
│   │   │   ├── face_routes.py    # /api/face/ — face enroll, verify
│   │   │   └── ocr.py            # /api/ocr/ — scan, retrieve OCR results
│   │   ├── services/             # Core business logic
│   │   │   ├── audit_service.py          # Write to audit_logs collection
│   │   │   ├── biometric_service.py      # User registration, JWT generation
│   │   │   ├── blockchain_service.py     # web3 calls to smart contract
│   │   │   ├── classification_service.py # Zero-shot document classifier
│   │   │   ├── embedding_service.py      # sentence-transformers + FAISS
│   │   │   ├── evaluator.py              # FUNSD evaluation pipeline
│   │   │   ├── export.py                 # Jinja2 → PDF via ReportLab
│   │   │   ├── face_recognition_service.py # dlib face embeddings
│   │   │   ├── generator.py              # LLM text generation
│   │   │   ├── metadata_service.py       # spaCy NER extraction
│   │   │   ├── metrics.py                # Evaluation metrics (F1, precision, recall)
│   │   │   ├── nlp_service.py            # NER + classification orchestrator
│   │   │   ├── ocr_engine.py             # Tesseract wrapper, unified output
│   │   │   ├── parser.py                 # Token → line → block grouping
│   │   │   ├── preprocess.py             # OpenCV image cleaning + caching
│   │   │   ├── rag_service.py            # FAISS retrieval + LLM context assembly
│   │   │   ├── summarization_service.py  # BART summarizer with map-reduce
│   │   │   └── validator.py              # Output structure validators
│   │   ├── templates/            # Jinja2 document templates
│   │   │   ├── affidavit.j2
│   │   │   ├── affidavit_general.j2
│   │   │   ├── employment_contract.j2
│   │   │   ├── fir.j2
│   │   │   ├── legal_notice.j2
│   │   │   ├── power_of_attorney.j2
│   │   │   └── rental_agreement.j2
│   │   └── tests/                # pytest test suite
│   ├── blockchain/               # Hardhat project
│   │   ├── contracts/
│   │   │   └── DocumentRegistry.sol   # Smart contract
│   │   ├── scripts/
│   │   │   ├── deploy.js              # Hardhat deploy script
│   │   │   └── deploy_simple.js       # Plain Node.js deploy (no Hardhat plugin)
│   │   ├── DocumentRegistry.abi.json  # Compiled ABI
│   │   ├── DocumentRegistry.address.txt  # Deployed contract address
│   │   └── hardhat.config.js
│   ├── esp32/
│   │   └── fingerprint_auth/
│   │       └── fingerprint_auth.ino   # Arduino firmware for ESP32
│   ├── scripts/
│   │   ├── run_on_image.py            # Run full pipeline on a single image
│   │   └── smoke_test.py              # Quick sanity check
│   └── requirements.txt
│
├── frontend/                     # Next.js 15 application
│   ├── src/
│   │   ├── app/
│   │   │   ├── landing/page.tsx       # Marketing landing page
│   │   │   ├── auth/
│   │   │   │   ├── login/page.tsx
│   │   │   │   ├── register/page.tsx
│   │   │   │   └── face-enroll/page.tsx
│   │   │   └── dashboard/
│   │   │       ├── page.tsx           # Dashboard home (stats, charts)
│   │   │       ├── ocr/page.tsx       # Document upload + OCR
│   │   │       ├── analysis/page.tsx  # AI analysis results
│   │   │       ├── documents/page.tsx # Document library
│   │   │       ├── search/page.tsx    # Semantic search
│   │   │       ├── chat/page.tsx      # RAG legal chatbot
│   │   │       ├── generate/page.tsx  # Document generation
│   │   │       ├── blockchain/page.tsx # Blockchain verification
│   │   │       └── settings/page.tsx
│   │   ├── components/
│   │   │   ├── layout/               # Sidebar, Navbar, DashboardLayout
│   │   │   ├── providers/            # ThemeProvider (next-themes)
│   │   │   ├── ui/                   # shadcn/ui components
│   │   │   └── WebcamCapture.tsx     # Face enrollment webcam component
│   │   ├── lib/
│   │   │   ├── api.ts                # Axios API client
│   │   │   └── utils.ts              # Utility functions
│   │   └── store/
│   │       └── useAppStore.ts        # Zustand global state
│   └── package.json
│
├── test/                         # Standalone test Flask app
│   └── app.py
├── start_backend.bat             # Windows one-click startup script
└── .gitignore
```

---

## Getting Started

### Prerequisites

- Python 3.11
- Node.js 18+
- MongoDB (running locally on default port 27017)
- Tesseract OCR installed and on PATH
- Git

### Backend Setup

```bash
# From the IDP/ directory
cd IDP

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start Flask backend
cd backend
python app.py
# Server starts at http://localhost:5000
```

On startup, the backend:
- Ensures MongoDB indexes exist
- Seeds 3 demo users (Judge, Police Officer, Lawyer) with fingerprint IDs 1, 2, 3

### Blockchain Setup

```bash
cd IDP/blockchain

# Install Hardhat dependencies
npm install

# Start local Hardhat node (keep this terminal open)
node_modules\.bin\hardhat.cmd node

# In a new terminal — deploy the smart contract
node scripts/deploy_simple.js
# Contract address saved to DocumentRegistry.address.txt
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
# Add NEXT_PUBLIC_API_URL=http://localhost:5000 to .env.local

# Start development server
npm run dev
# App available at http://localhost:3000
```

### Quick Start (Windows)

A single batch script starts everything:

```bat
start_backend.bat
```

This will:
1. Start the Hardhat local blockchain node on port 8545
2. Deploy the `DocumentRegistry` smart contract
3. Start the Flask backend on port 5000

Then start the frontend separately with `npm run dev` in the `frontend/` folder.

---

## API Reference

### Biometric Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/biometric/register` | No | Register a user with a fingerprint ID |
| POST | `/api/biometric/authenticate` | No | Authenticate and receive a JWT |
| GET | `/api/biometric/profile` | Bearer JWT | Get profile from token claims |
| GET | `/api/biometric/demo-users` | No | List demo users (name + role) |
| POST | `/verify` | No | ESP32-facing endpoint; returns authorized/unauthorized |

**Authenticate**
```json
// POST /api/biometric/authenticate
// Request
{ "fingerprint_id": 1 }

// Response 200
{ "token": "eyJhbGci...", "name": "Judge A", "role": "judge" }
```

---

### OCR Endpoint

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/ocr/scan` | Optional | Upload document, run full AI pipeline |

```
POST /api/ocr/scan
Content-Type: multipart/form-data
file: <document.pdf / .png / .jpg>
lang: eng  (optional)
```

```json
// Response 200
{
  "document_id": "64a1b2c3d4e5f6789012abcd",
  "document_type": "FIR",
  "summary": "FIR filed by complainant against accused...",
  "metadata": {
    "case_number": "CR/123/2024",
    "persons": ["John Doe", "Jane Smith"],
    "dates": ["01-Jan-2024"],
    "ipc_sections": ["Section 420"]
  },
  "blockchain": {
    "document_hash": "sha256:abc123...",
    "transaction_hash": "0xdef456...",
    "registered": true
  }
}
```

---

### AI / RAG Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/ai/query` | Optional | RAG query over indexed documents |

```json
// POST /api/ai/query
// Request
{
  "query": "What are the penalty clauses in this contract?",
  "doc_id": "64a1b2c3d4e5f6789012abcd",
  "top_k": 5
}

// Response 200
{
  "answer": "Section 12 specifies a penalty of ₹50,000...",
  "source_chunks": [
    { "doc_id": "...", "chunk_id": "...", "score": 0.91 }
  ]
}
```

---

### Blockchain Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/blockchain/register` | Bearer JWT | Register document hash on-chain |
| POST | `/api/blockchain/verify` | Bearer JWT | Verify document integrity |
| GET | `/api/blockchain/document/<id>` | Bearer JWT | Get on-chain record |

```json
// POST /api/blockchain/verify
// Request
{ "document_id": "64a1b2c3d4e5f6789012abcd" }

// Response 200 — authentic
{ "document_id": "...", "document_hash": "sha256:abc123...", "status": "authentic" }

// Response 200 — tampered
{ "status": "tampered", "expected_hash": "...", "stored_hash": "..." }
```

---

### Document Generation

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/documents/create` | Bearer JWT | Generate a legal document from template |

---

### Face Recognition

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/face/enroll` | Bearer JWT | Enroll a face from webcam image |
| POST | `/api/face/verify` | No | Verify face image against enrolled embedding |

---

## Authentication & Security

The system uses a layered security model:

**JWT Middleware** (`backend/middleware/auth.py`)
- Applied to all `/api/blockchain/*` and `/api/documents/*` routes
- Expects `Authorization: Bearer <token>` header
- Returns `401` for missing, malformed, or expired tokens

**Token Generation** (`backend/services/biometric_service.py`)
- Tokens are HS256-signed JWTs with 1-hour expiry
- Claims: `user_id`, `name`, `role`, `iat`, `exp`
- Secret configured via `JWT_SECRET` environment variable (default is a placeholder — **change before production**)

**Demo Users** (seeded on startup)

| Name | Fingerprint ID | Role |
|---|---|---|
| Judge A | 1 | judge |
| Police Officer | 2 | police |
| Lawyer | 3 | lawyer |

**Audit Logging**
Every login, document upload, view, and verification writes a record to `audit_logs`:
```json
{
  "user": "Judge A",
  "role": "judge",
  "action": "verify_document",
  "document_id": "...",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Blockchain Integration

The `DocumentRegistry.sol` smart contract exposes two functions:
- `registerDocument(bytes32 hash, string docId)` — stores the hash on-chain
- `verifyDocument(bytes32 hash)` — returns true if the hash was previously registered

The Flask `blockchain_service.py` interacts with the contract using `web3.py`. The contract address is read from `blockchain/DocumentRegistry.address.txt` after deployment.

**Tamper Detection Flow:**
1. Document text is extracted via OCR and stored in MongoDB
2. SHA-256 hash of that text is registered on-chain
3. On verify: recompute hash from stored text → compare with on-chain record
4. Any modification to the document text will produce a different hash → tamper detected

---

## Hardware (ESP32 Fingerprint)

The `esp32/fingerprint_auth/fingerprint_auth.ino` firmware:
- Reads from a fingerprint sensor on UART2 (GPIO 16 RX, GPIO 17 TX, 57600 baud)
- On a successful match, sends `POST http://<server-ip>:5000/verify` with `{ "fingerprint_id": <id>, "confidence": <score> }`
- Displays authentication status on serial monitor

The backend `/verify` endpoint returns:
```json
{ "status": "authorized", "user": "Judge A", "confidence": 150 }
```
or
```json
{ "status": "unauthorized", "user": "Unknown" }
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | `change-me-in-production` | Secret for signing JWTs. Must be changed before deployment |
| `OCR_BACKEND` | `tesseract` | OCR engine: `tesseract`, `easyocr`, or `cloud` |
| `EMBEDDING_MODEL` | — | HuggingFace model ID for sentence embeddings |
| `GENERATOR_MODEL` | — | LLM model name for RAG generation |
| `FAISS_INDEX_DIR` | `backend/faiss_index/` | Directory for FAISS index files |
| `CACHE_DIR` | `backend/preprocessed_cache/` | Directory for cached preprocessed images |
| `DEBUG` | `0` | Set to `1` to enable Flask debug mode |
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `NEXT_PUBLIC_API_URL` | — | Backend URL for the Next.js frontend |

---

## Running Tests

```bash
cd IDP

# Activate your virtualenv first
venv\Scripts\activate

# Run all tests
pytest -q

# Run with verbose output
pytest -v

# Run a specific test file
pytest backend/tests/test_classify.py

# Run integration tests
python backend/run_integration_tests.py
```

Tests use mocks and fixtures defined in `backend/tests/conftest.py`. Set `TEST_MODE=1` to skip heavy model loading and use lightweight stubs instead.

**Test Coverage**
- `test_classify.py` — document classification service
- `test_chunking.py` — text chunking logic
- `test_detect_clauses.py` — clause detection
- `test_embedding_service.py` — FAISS embedding and retrieval
- `test_extract_entities.py` — NER entity extraction
- `test_rag_service.py` — RAG pipeline end-to-end
- `test_risk_check.py` — risk analysis flags
- `test_summarize.py` — summarization output
- `test_biometric_auth.py` — fingerprint auth and JWT flow
- `test_ai_blueprint.py` — AI route integration tests

---

## Module Status

| Module | Status |
|---|---|
| OCR Processing | ✅ Complete |
| Document Classification | ✅ Complete |
| Metadata / NER Extraction | ✅ Complete |
| Summarization | ✅ Complete |
| Risk Analysis | ✅ Complete |
| Semantic Search (FAISS) | ✅ Complete |
| RAG Chatbot | ✅ Complete |
| Document Generation (Templates) | ✅ Complete |
| MongoDB Storage | ✅ Complete |
| Blockchain Registration | ✅ Complete |
| Blockchain Verification | ✅ Complete |
| ESP32 Fingerprint Auth | ✅ Complete |
| Face Recognition 2FA | ✅ Complete |
| JWT Auth Middleware | ✅ Complete |
| Audit Logging | ✅ Complete |
| Next.js Frontend Dashboard | ✅ Complete |
| FUNSD Evaluation Pipeline | ✅ Complete |

---

## Known Issues & Notes

- The default `JWT_SECRET` is `"change-me-in-production"` — set the `JWT_SECRET` environment variable before any real deployment.
- `/api/ocr/scan` is not JWT-protected by default. Add `"/api/ocr/"` to `PROTECTED_PREFIXES` in `middleware/auth.py` to require auth for uploads.
- The FAISS index is built in-memory and persisted to disk. If the index directory is empty, run the embedding service's index-build step before using semantic search.
- The blockchain node must be running before starting the Flask backend, or blockchain-related endpoints will return connection errors.
