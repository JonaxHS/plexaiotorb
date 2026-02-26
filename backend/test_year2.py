import re

def check_year_mismatch(item_name, expected_year):
    str_year = str(expected_year).strip() if expected_year else ""
    if str_year:
        years_in_name = re.findall(r'\b(19\d{2}|20\d{2})\b', item_name)
        if years_in_name and str_year not in years_in_name:
            return True # Mismatch!
    return False

test_cases = [
    ("Avatar.2009.1080p.mkv", "2009"),
    ("Avatar.Fire.and.Ash.2025.1080p.CAMRip.mkv", "2009"),
    ("Super.Movie.1080p.mkv", "2009"),
    ("Movie.2000.2008.mkv", "2008"),  # Title might have a year number
]

for name, expected in test_cases:
    print(f"{name} vs {expected}: Mismatch? {check_year_mismatch(name, expected)}")
