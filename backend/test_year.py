from watcher import is_valid_match

# True positive test
print("Avatar vs Avatar 2009:", is_valid_match("Avatar.2009.1080p.mkv", "Avatar.mkv", "Avatar", "2009", None, None))

# False positive test (Avatar 2025 matching Avatar 2009)
print("Avatar: Fire and Ash 2025 vs Avatar 2009:", is_valid_match("Avatar.Fire.and.Ash.2025.1080p.CAMRip.mkv", "Avatar.mkv", "Avatar", "2009", None, None))
