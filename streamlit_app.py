# streamlit_app.py
# ─────────────────────────────────────────────────────────────
# Streamlit Community Cloud requires the entry point to be
# named 'streamlit_app.py' at the repository root.
# This file simply imports and delegates to app.py so the
# project structure stays clean.
# ─────────────────────────────────────────────────────────────
from app import main

if __name__ == "__main__":
    main()
