import os

def clean_name(name: str) -> str:
    for c in ['.', '-', '_', '+', ' ', '[', ']', '(', ')', ':']:
        name = name.replace(c, '')
    return name.lower()

def is_valid_match(item_name: str, expected_filename: str, title: str, year: str) -> bool:
    if not item_name: return False
    item_clean = clean_name(os.path.splitext(item_name)[0])
    expected_clean = clean_name(os.path.splitext(expected_filename)[0])
    title_clean = clean_name(title)
    str_year = str(year).strip() if year else ""
    
    print(f"item_clean: {item_clean}")
    print(f"expected_clean: {expected_clean}")
    print(f"title_clean: {title_clean}, year: {str_year}")
    
    if expected_filename.lower() == item_name.lower(): return True
    if len(expected_clean) > 5 and (expected_clean in item_clean or item_clean in expected_clean): return True
    
    if title_clean and title_clean in item_clean:
        if str_year and str_year in item_clean: return True
        elif not str_year and len(title_clean) > 3: return True
            
    return False

item_name = "Fast.X.2023.1080p.REMUX.ENG.And.ESP.LATINO.Multi.Sub.TrueHD.Atmos.x264.MKV-BEN.THE.MEN"
expected_filename = "Fast.X.2023.1080p.REMUX.ENG.And.ESP.LATINO.Multi.Sub.TrueHD.Atmos.x264.MKV-BEN.THE.MEN.mkv"
title = "Rápidos y furiosos X"
year = "2023"

print("Match:", is_valid_match(item_name, expected_filename, title, year))
