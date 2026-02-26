import re
from watcher import is_valid_match

test_cases = [
    # original name on TorBox vs TMDB localized vs Expected (from AIOStreams)
    ("Game of Thrones iNTEGRALE MULTi 2160p HDR BluRay x265-QTZ", "Game of Thrones S01E02.mkv", "Juego de Tronos", "2011", 1, 2),
    ("Agatha.Christie.Las.Siete.Esferas.S01E02.2026.1080p-Dual-Lat", "Agatha Christie's The Seven Dials Mystery S01E02.mkv", "El misterio de las siete esferas", "2026", 1, 2)
]

for item, expected, title, year, season, episode in test_cases:
    res = is_valid_match(item, expected, title, year, season, episode)
    print(f"Match: {res} | Item: {item}")
