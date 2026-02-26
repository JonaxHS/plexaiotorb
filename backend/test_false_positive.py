import re
from watcher import is_valid_match

# title = Exterminio, item = dexter.s01...
res = is_valid_match("Dexter.S01E01.2006.WEB-DL.1080p-Dual-Lat.mkv", "[RD+] TorBox", "Exterminio", "2026", None, None)
print(f"Match: {res}")
