from media_utils import extract_se_info, get_match_score, is_valid_match

tests = [
    # (name, expected_filename, title, year, season, episode, original_title)
    ("Ted.2024.S01E01.mkv", "Ted.S01E01.mkv", "Ted", "2024", 1, 1, "Ted"),
    ("Ted.2012.1080p.mkv", "Ted.2012.mkv", "Ted", "2012", None, None, "Ted"),
    ("Los.Ilusionistas.2.2016.mkv", "Now.You.See.Me.2.mkv", "Los Ilusionistas 2", "2016", None, None, "Now You See Me 2"),
    ("X-Men.97.S01E02.mkv", "X-Men.97.S01E02.mkv", "X-Men '97", "2024", 1, 2, "X-Men '97"),
    ("The.Trisolaris.S01E05.mkv", "3.Body.Problem.S01E05.mkv", "El problema de los 3 cuerpos", "2024", 1, 5, "3 Body Problem"),
]

for name, exp, title, year, s, e, orig in tests:
    score = get_match_score(name, exp, title, year, s, e, orig)
    valid = is_valid_match(name, exp, title, year, s, e, orig)
    se = extract_se_info(name)
    print(f"Name: {name:40} | Score: {score:3} | Valid: {str(valid):5} | S/E: {se}")
