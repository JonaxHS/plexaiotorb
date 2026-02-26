import re

def clean_words(name):
    if not name: return []
    res = re.sub(r'[^a-zA-Z0-9]', ' ', name).lower()
    return res.split()

item = "Dexter.S01E01.2006.WEB-DL.1080p-Dual-Lat.mkv"
title = "Exterminio"
expected = "28 Years Later"

item_w = clean_words(item)
title_w = clean_words(title)
expected_w = clean_words(expected)

def has_word_match(target_words, query_words):
    if not query_words: return False
    # Check if first word of query is in target words
    return query_words[0] in target_words

print("Dexter vs Exterminio:", has_word_match(clean_words("Dexter.S01E01"), clean_words("Exterminio")))
print("Agatha vs Agatha:", has_word_match(clean_words("Agatha.Christie.Las.Siete.Esferas"), clean_words("Agatha Christie's The Seven")))
