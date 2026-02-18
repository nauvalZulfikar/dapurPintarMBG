# MBG Dapur Pintar – Phase 1 (Minimal Bot)

## 1) Setup
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
python init_db.py
cp .env.example .env   # fill in tokens/IDs
 