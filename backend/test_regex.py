import re

def extract_se_info(text: str):
    if not text: return None, None
    match = re.search(r'[sS](\d+)[eE](\d+)', text)
    if match: return int(match.group(1)), int(match.group(2))
    # Limitar season a 1 o 2 digitos para no chocar con resoluciones (ej 720x480)
    match = re.search(r'(?<!\d)(\d{1,2})x(\d{1,3})(?!\d|\w)', text, re.I)
    if match: return int(match.group(1)), int(match.group(2))
    return None, None

print(extract_se_info("Ted.1920x1080.mkv"))
print(extract_se_info("Movie.1080x720.mkv"))
print(extract_se_info("Movie.720x480.mkv"))
print(extract_se_info("Show.1x02.mkv"))
print(extract_se_info("X-Men.2x02.mkv"))
print(extract_se_info("x264.1x03.mkv"))
