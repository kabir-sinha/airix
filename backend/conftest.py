# backend/conftest.py
"""
conftest.py
Points every test at a throwaway SQLite file instead of the real
airix.db, and does it at import time (module-level, not inside a
fixture function) so it takes effect before database.py or main.py are
first imported by any test module.
"""
import os
import tempfile

_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["AIRIX_DB_URL"] = f"sqlite:///{_tmp_db.name}"
