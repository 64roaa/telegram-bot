import io
import zipfile
import hashlib
import logging
from typing import Tuple, List

logger = logging.getLogger(__name__)

def detect_file_type(data: bytes, filename: str) -> Tuple[str, str]:
    magic = data[:8]
    if magic[:2] == b'MZ': return "application/x-msdownload", "exe"
    if magic[:4] == b'%PDF': return "application/pdf", "pdf"
    if magic[:4] in (b'PK\x03\x04', b'PK\x05\x06'): return "application/zip", "zip"
    if magic[:4] == b'\x7fELF': return "application/x-elf", "elf"
    if magic[:3] == b'\xff\xd8\xff': return "image/jpeg", "jpg"
    if magic[:8] == b'\x89PNG\r\n\x1a\n': return "image/png", "png"
    return "application/octet-stream", "bin"

def deep_analysis(data: bytes, filename: str, real_ext: str) -> List[str]:
    warns = []
    declared = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if declared in ("pdf", "jpg", "png") and real_ext in ("exe", "elf", "dll"):
        warns.append(f"🚨 إخفاء امتداد! يبدو {declared.upper()} لكنه {real_ext.upper()}")
    
    if real_ext in ("zip", "jar"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = zf.namelist()
                if "AndroidManifest.xml" in names:
                    warns.append("📱 APK — تطبيق Android")
                exe_in = [n for n in names if n.lower().endswith((".exe", ".dll", ".bat"))]
                if exe_in: warns.append(f"🚨 ZIP يحتوي: {', '.join(exe_in[:3])}")
        except Exception: pass
    return warns
