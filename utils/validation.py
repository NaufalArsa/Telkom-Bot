import re
from typing import Dict, List, Tuple
from config import REQUIRED_FIELDS

# Regex pattern for caption parsing
CAPTION_PATTERN = re.compile(r"""
    Nama\s+SA/\s*AR:\s*(?P<nama_sa>.*?)\n+
    STO:\s*(?P<sto>.*?)\n+
    Cluster:\s*(?P<cluster>.*?)\n+
    \n*
    Nama\s+usaha:\s*(?P<usaha>.*?)\n+
    Nama\s+PIC:\s*(?P<pic>.*?)\n+
    Nomor\s+HP/\s*WA:\s*(?P<hpwa>.*?)\n+
    Internet\s+existing:\s*(?P<internet>.*?)\n+
    Biaya\s+internet\s+existing:\s*(?P<biaya>.*?)\n+
    Voice\s+of\s+Customer:\s*(?P<voc>.*?)(?:\n|$)
""", re.DOTALL | re.MULTILINE | re.IGNORECASE | re.VERBOSE)

def validate_caption_data(row: Dict[str, str]) -> Tuple[bool, List[str], str]:
    """Validate caption data fields"""
    missing_fields = []
    
    for field_key, field_name in REQUIRED_FIELDS.items():
        field_value = row.get(field_key, '').strip()
        if not field_value:
            missing_fields.append(field_name)
    
    if missing_fields:
        error_message = f"❌ **Data tidak lengkap!**\n\nField yang masih kosong:\n"
        for i, field in enumerate(missing_fields, 1):
            error_message += f"{i}. {field}\n"
        error_message += "\n📝 **Langkah selanjutnya:**\nLengkapi field yang kosong di atas, kemudian kirim ulang data."
        return False, missing_fields, error_message
    
    return True, [], "✅ Semua data lengkap!"

def extract_markdown_link(text: str) -> str:
    """Extract URL from markdown link format [text](url)"""
    md_match = re.match(r'\[.*?\]\((https?://[^\)]+)\)', text)
    return md_match.group(1) if md_match else text 