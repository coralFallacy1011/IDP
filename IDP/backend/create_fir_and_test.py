"""
End-to-end real document test:
1. Generate a FIR PDF
2. Authenticate as Judge A (fingerprint_id=1) → get JWT
3. POST the FIR PDF to /api/ocr/scan
4. Verify the document on blockchain
5. Check audit logs
"""
import sys, os, json, time
import io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Step 0: Generate FIR PDF in memory ───────────────────────────────────────
print("=" * 60)
print("  STEP 0: Generating FIR PDF")
print("=" * 60)

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image, ImageDraw, ImageFont
import textwrap

fir_text = """FIRST INFORMATION REPORT (FIR)

Police Station: Kotwali, Delhi
FIR Number: CR/456/2024
Date: 15-January-2024

To,
The Station House Officer,
Kotwali Police Station, Delhi.

Subject: Complaint regarding Theft and Assault

I, Rajesh Kumar, son of Mohan Kumar, aged 42 years, residing at
House No. 45, Gandhi Nagar, New Delhi - 110031, wish to lodge a
complaint regarding the following incident:

Date of Incident: 14-January-2024
Time: 21:30 hours
Location: Gandhi Nagar Market, New Delhi

Details:
On the above mentioned date and time, while I was returning home
from Gandhi Nagar Market, two unknown persons intercepted me near
the market gate. One of them, aged approximately 25-30 years,
wearing a black jacket, snatched my mobile phone (Samsung Galaxy S23)
and wallet containing cash of Rs. 15,000 and important documents
including Aadhar Card and PAN Card.

When I resisted, the accused persons assaulted me causing injuries
to my left arm. The accused fled on motorcycle bearing DL-7C-5678.

Witnesses: Mr. Suresh Verma and Mrs. Anita Singh were present.

Sections Applicable: IPC Section 392 (Robbery), IPC Section 323 (Assault)

I request you to register my complaint and take necessary legal action.

Yours faithfully,
Rajesh Kumar
Contact: 9876543210
Date: 15-January-2024
Place: New Delhi
"""

# Generate PNG image (avoids poppler dependency)
img_width, img_height = 794, 1123  # A4 at 96dpi
img = Image.new("RGB", (img_width, img_height), color="white")
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 16)
    font_bold = ImageFont.truetype("arialbd.ttf", 18)
except Exception:
    font = ImageFont.load_default()
    font_bold = font

y_pos = 40
for line in fir_text.strip().split('\n'):
    wrapped = textwrap.wrap(line, width=90) if line.strip() else ['']
    for wline in wrapped:
        f = font_bold if y_pos < 80 else font
        draw.text((40, y_pos), wline, fill="black", font=f)
        y_pos += 22
    if not line.strip():
        y_pos += 5

fir_img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fir_CR456_2024.png")
os.makedirs(os.path.dirname(fir_img_path), exist_ok=True)
img.save(fir_img_path)
print(f"  FIR PNG generated: {fir_img_path}")

with open(fir_img_path, "rb") as f:
    fir_bytes = f.read()
fir_filename = "fir_CR456_2024.png"

# ── Build Flask test app ──────────────────────────────────────────────────────
from flask import Flask
from routes.biometric import biometric_bp
from routes.blockchain import blockchain_bp
from routes.ocr import ocr_bp
from middleware.auth import init_auth
from models.document import db

app = Flask(__name__)
app.config["TESTING"] = True
# Register biometric routes (no auth needed)
app.register_blueprint(biometric_bp, url_prefix="/api/biometric")
# Register OCR and blockchain (protected)
app.register_blueprint(ocr_bp, url_prefix="/api/ocr")
app.register_blueprint(blockchain_bp, url_prefix="/api/blockchain")
init_auth(app)
client = app.test_client()

# ── Step 1: Authenticate ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  STEP 1: Fingerprint Authentication (ID=1 → Judge A)")
print("=" * 60)

r_auth = client.post("/api/biometric/authenticate", json={"fingerprint_id": 1})
auth_body = r_auth.get_json() or {}
print(f"  Status  : {r_auth.status_code}")
print(f"  Name    : {auth_body.get('name')}")
print(f"  Role    : {auth_body.get('role')}")
print(f"  Token   : {str(auth_body.get('token',''))[:50]}...")

assert r_auth.status_code == 200 and "token" in auth_body, "AUTH FAILED"
jwt_token = auth_body["token"]
headers = {"Authorization": f"Bearer {jwt_token}"}
print("  → PASS")

# ── Step 2: Upload FIR PDF to OCR endpoint ────────────────────────────────────
print("\n" + "=" * 60)
print("  STEP 2: Upload FIR PDF to /api/ocr/scan")
print("=" * 60)

r_ocr = client.post(
    "/api/ocr/scan",
    data={"file": (io.BytesIO(fir_bytes), fir_filename), "lang": "eng"},
    content_type="multipart/form-data"
)
ocr_body = r_ocr.get_json() or {}

print(f"  Status        : {r_ocr.status_code}")
print(f"  Document ID   : {ocr_body.get('document_id', 'N/A')}")
print(f"  Document Type : {ocr_body.get('document_type', 'N/A')}")
print(f"  Summary       : {str(ocr_body.get('summary',''))[:120]}")
print(f"  Metadata      :")
metadata = ocr_body.get("metadata", {})
for k, v in metadata.items():
    if v:
        print(f"    {k}: {v}")
bc = ocr_body.get("blockchain", {})
print(f"  Blockchain    :")
print(f"    Hash        : {str(bc.get('document_hash',''))[:50]}")
print(f"    Tx Hash     : {str(bc.get('transaction_hash',''))[:50]}")
print(f"    Registered  : {bc.get('registered')}")

if r_ocr.status_code == 200:
    document_id = ocr_body.get("document_id")
    print("  → PASS")
else:
    print(f"  → FAIL: {ocr_body.get('error','unknown error')}")
    document_id = None

# ── Step 3: Blockchain Verification ──────────────────────────────────────────
if document_id:
    print("\n" + "=" * 60)
    print("  STEP 3: Blockchain Verification")
    print("=" * 60)

    r_verify = client.post(
        "/api/blockchain/verify",
        json={"document_id": document_id},
        headers=headers
    )
    v_body = r_verify.get_json() or {}
    print(f"  Status        : {r_verify.status_code}")
    print(f"  Document ID   : {v_body.get('document_id')}")
    print(f"  Hash          : {str(v_body.get('document_hash',''))[:50]}")
    print(f"  Status        : {v_body.get('status')}")
    print(f"  → {'PASS' if v_body.get('status') == 'authentic' else 'CHECK: ' + str(v_body)}")

# ── Step 4: Audit Logs ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  STEP 4: Audit Log Entries")
print("=" * 60)
logs = list(db["audit_logs"].find({}, {"_id": 0}).sort("timestamp", -1).limit(5))
for l in logs:
    print(f"  user={l.get('user')}  role={l.get('role')}  "
          f"action={l.get('action')}  doc={l.get('document_id')}  "
          f"ts={str(l.get('timestamp'))[:19]}")
print(f"  → {'PASS' if logs else 'No logs yet'}")

# ── Step 5: MongoDB Document Record ──────────────────────────────────────────
if document_id:
    print("\n" + "=" * 60)
    print("  STEP 5: MongoDB Document Record")
    print("=" * 60)
    from bson import ObjectId
    doc = db["documents"].find_one({"_id": ObjectId(document_id)})
    if doc:
        print(f"  _id           : {doc['_id']}")
        print(f"  filename      : {doc.get('filename')}")
        print(f"  doc_type      : {doc.get('classification', {}).get('document_type')}")
        print(f"  lang          : {doc.get('lang')}")
        print(f"  ocr_clean len : {len(doc.get('ocr_text', {}).get('clean', ''))} chars")
        print(f"  blockchain    : registered={doc.get('blockchain', {}).get('registered')}")
        print("  → PASS")

print("\n" + "=" * 60)
print("  END-TO-END TEST COMPLETE")
print("=" * 60)
