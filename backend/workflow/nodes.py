# cv-agent/backend/workflow/nodes.py

"""
LangGraph node functions untuk CV Agent workflow.

Setiap node adalah async function yang:
1. Menerima CVAgentState sebagai input
2. Melakukan satu unit pekerjaan (LLM call, DB query, atau kalkulasi)
3. Mengembalikan dict berisi HANYA field state yang berubah

LangGraph otomatis merge partial dict ini ke full state —
node tidak perlu return seluruh state, hanya yang berubah.

Phase 5: semua node adalah stubs dengan placeholder data berstruktur benar.
Phase 6: setiap stub diganti dengan real LLM agent call.
"""

import logging
from datetime import datetime, timezone

from config import get_settings
from db.supabase import get_supabase
from workflow.state import CVAgentState

# ── Logger ────────────────────────────────────────────────────────────────────
# Module-level logger — dipakai oleh semua node di file ini
# Format: "workflow.nodes" sebagai logger name untuk mudah difilter di log output
# Contoh log: "workflow.nodes - INFO - [parse_jd_jr] called for application uuid-123"

logger = logging.getLogger("workflow.nodes")

# ── Node functions akan ditambahkan di substep 2.2 sampai 2.9 ─────────────────