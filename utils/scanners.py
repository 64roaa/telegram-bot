import re
import aiohttp
import asyncio
import logging
import time
import hashlib
from typing import Optional, Tuple, Any, Dict
import database as db
from config import cfg

logger = logging.getLogger(__name__)

# Threshold constants - no circular imports needed
VT_MALICIOUS_THRESHOLD = 5

# Memory cache for scan results
_SCAN_CACHE: Dict[str, Tuple[Optional[str], float]] = {}
CACHE_TTL = 3600  # 1 hour

def _get_from_cache(key: str) -> Optional[Any]:
    if key in _SCAN_CACHE:
        val, expiry = _SCAN_CACHE[key]
        if time.time() < expiry:
            return val
        else:
            del _SCAN_CACHE[key]
    return None

def _set_in_cache(key: str, val: Any) -> None:
    _SCAN_CACHE[key] = (val, time.time() + CACHE_TTL)

# URL Patterns for basic checks
SUSPICIOUS_URL_PATTERNS = [
    (r"bit\.ly|tinyurl|t\.co|goo\.gl", "رابط مختصر (يُشتبه في إخفاء الوجهة)"),
    (r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "عنوان IP مباشر (غير معتاد للمواقع الموثوقة)"),
    (r"login|verify|secure|update|password", "كلمات تستخدم غالباً في التصيّد"),
    (r"\.xyz|\.top|\.tk|\.ml|\.ga", "نطاق ذو سمعة منخفضة"),
    (r"@", "يحتوي على رمز @ (محاولة تضليل)"),
]

async def _async_request(method: str, url: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    """دالة موحدة للاتصالات الخارجية مع معالجة الأخطاء."""
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, timeout=10, **kwargs) as resp:
                    if resp.status in (200, 201):
                        return await resp.json()
                    logger.warning(f"API {url} returned {resp.status} on attempt {attempt+1}")
        except Exception as e:
            logger.error(f"API {url} error on attempt {attempt+1}: {e}")
        await asyncio.sleep(1)
    return None

async def check_google_safebrowsing(url: str) -> Optional[str]:
    """Check URL against Google Safe Browsing API. Implements Cache."""
    cache_key = f"sb_{url}"
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result if cached_result != "CLEAN" else None

    if not cfg.SAFE_BROWSING_KEY:
        return None
    
    api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={cfg.SAFE_BROWSING_KEY}"
    body = {
        "client": {"clientId": "amanteech-bot", "clientVersion": "5.1"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        }
    }
    
    data = await _async_request("POST", api_url, json=body)
    result = None
    if data and data.get("matches"):
        result = data["matches"][0]["threatType"]
    
    _set_in_cache(cache_key, result if result else "CLEAN")
    return result

async def scan_url_virustotal(url: str) -> Tuple[str, str]:
    """Perform a full VirusTotal URL scan. Implements Cache."""
    cache_key = f"vt_{url}"
    cached_result = _get_from_cache(cache_key)
    if cached_result is not None:
        return cached_result
        
    if not cfg.VIRUSTOTAL_KEY:
        return "آمن (فحص دقيق معطل)", "آمن"
    
    headers = {"x-apikey": cfg.VIRUSTOTAL_KEY}
    
    # 1. Submission
    post_data = await _async_request("POST", "https://www.virustotal.com/api/v3/urls", headers=headers, data={"url": url})
    if not post_data:
        return "فشل الاتصال بخوادم الفحص. جرب لاحقاً.", "خطأ"
    
    analysis_id = post_data["data"]["id"]
    await asyncio.sleep(4)
    
    analysis_url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
    results = await _async_request("GET", analysis_url, headers=headers)
    
    if not results:
        return "المعذرة، لم نتمكن من جلب نتيجة الفحص.", "خطأ"
        
    stats = results["data"]["attributes"]["stats"]
    malicious = stats.get("malicious", 0)
    suspicious = stats.get("suspicious", 0)
    

    if malicious > VT_MALICIOUS_THRESHOLD:
        final_verdict = ("🔴 *الرابط خبيث جداً!*\nالسبب: تقارير تؤكد احتوائه على برمجيات ضارة.", "ضار")
    elif malicious > 0 or suspicious > 0:
        final_verdict = ("🟡 *الرابط مشبوه!*\nالسبب: بعض المؤشرات تدل على خطره المحتمل.", "مشبوه")
    else:
        final_verdict = ("🟢 *الرابط آمن!*\nالسبب: جميع الفحوصات نظيفة ولا يوجد خطر.", "آمن")
        
    _set_in_cache(cache_key, final_verdict)
    return final_verdict

async def scan_file_hash_vt(file_bytes: bytes) -> Tuple[str, str]:
    """Quick hash-based lookup on VirusTotal."""
    if not cfg.VIRUSTOTAL_KEY:
        return "آمن (فحص دقيق معطل)", "آمن"
        
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    cache_key = f"hash_{file_hash}"
    cached = _get_from_cache(cache_key)
    if cached: return cached
    
    headers = {"x-apikey": cfg.VIRUSTOTAL_KEY}
    url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
    
    data = await _async_request("GET", url, headers=headers)
    if not data or "data" not in data:
        res = ("🟢 *الملف غير معروف سابقاً لـ VT*\nالسبب: لم يتم العثور على توقيع مطابق في قاعدة البيانات العالمية.", "آمن")
    else:
        stats = data["data"]["attributes"]["last_analysis_stats"]
        malicious = stats.get("malicious", 0)
        if malicious > VT_MALICIOUS_THRESHOLD:
            res = ("🔴 *الملف خبيث!*\nالسبب: تم التعرف عليه كبرمجية ضارة من عدة محركات عالمية.", "ضار")
        else:
            res = ("🟢 *الملف سليم غالباً*\nالسبب: لم ترصده المحركات العالمية كتهديد.", "آمن")
            
    _set_in_cache(cache_key, res)
    return res

async def yara_scan_mock(file_path: str) -> list[str]:
    """Mock YARA scanning process."""
    # This would normally load compiled rules and scan
    # For now, it's a structural placeholder for the SaaS version
    return []

async def analyze_image_metadata(file_path: str) -> str:
    """Mock image metadata/EXIF/Stego analysis."""
    return "نظيف"

