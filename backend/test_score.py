import re
from watcher import get_match_score

test_cases = [
    ("Dexter.S01E07.2006.WEB-DL.1080p-Dual-Lat.mkv", "Dexter S01E07.mkv", "Dexter", "2006", 1, 7),
    ("Exterminio.La.evolucion.2025.WEB-DL.1080p-Dual-Lat.mkv", "[RD+] TorBox", "Exterminio", "2025", None, None)
]

for name, expected, title, year, season, episode in test_cases:
    score = get_match_score(name, expected, title, year, season, episode)
    print(f"Score: {score} | Item: {name} | Expected: {expected}")
