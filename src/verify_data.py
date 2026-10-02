"""
verify_data.py
--------------
Step 1 of the Sports Arena pipeline.

This script checks that the data files on your computer are EXACTLY the same
as the ones the project was built with. It does this using a SHA-256 checksum.

Files checked:
  data/merged/   the merged 2008-2026 dataset (the single source of truth)
  data/          the player-name map and the Impact Player list
  data/source/   the published explorer page the merged files were recovered from
  data/raw/      the original Kaggle 2008-2019 files (kept for reference)

What is a checksum?
    A checksum is a long "fingerprint" calculated from every byte of a file.
    If even one character in the file changes, the fingerprint changes
    completely. So if our fingerprints match, the files are identical.

Run it with:
    python src/verify_data.py
"""

import hashlib   # built into Python, used to calculate SHA-256 fingerprints
import os        # built into Python, used to build file paths
import sys       # built into Python, used to exit with an error code


# Folder that holds this script (src/), and the project folder above it.
SCRIPT_FOLDER = os.path.dirname(os.path.abspath(__file__))
PROJECT_FOLDER = os.path.dirname(SCRIPT_FOLDER)
DATA_FOLDER = os.path.join(PROJECT_FOLDER, "data")

# The fingerprints we recorded when the project was built (file path inside data/).
# These same values are written in data/README.md.
EXPECTED_CHECKSUMS = {
    "merged/matches_2008_2026.csv": "a2ed25f1be44d4986aa98875e85096e44b3bf4defdc3ce5a5044c8dc037307a6",
    "merged/deliveries_2008_2026.csv": "81c69222b95fcb3755b4de6e92df6aef5fc5a3480d0ff98b71186ff563406736",
    "player_name_map.csv": "21505be19e2d0fbfc240b434d4664230323071d32f6ef176473c69b576e756f8",
    "impact_players_2020_2026.csv": "ef45b304787c7736f75cfffa001e76c730a8b0058cfea5a7aac1a785e3774f34",
    "source/ipl_2008_2026_explorer.html.gz": "e18f126c1e5034deb8d7846679de3c62f2af1cf5840e59b1c639c6cad8248d6d",
    "raw/matches.csv": "57241c8438ce93f1824e8a07f779dc1c588687cc8afa344b2974518ad35195cb",
    "raw/deliveries.csv": "412dca480d2bfd89138828331d45d687c29d7fb402f6b002803dd16952107314",
}


def sha256_of_file(file_path):
    """Return the SHA-256 fingerprint of one file as a text string."""
    hasher = hashlib.sha256()
    # Open in "rb" = read binary mode, so we read the raw bytes.
    with open(file_path, "rb") as file:
        # Read the file in small pieces (1 MB) so big files do not fill memory.
        while True:
            piece = file.read(1024 * 1024)
            if not piece:          # an empty piece means we reached the end
                break
            hasher.update(piece)
    return hasher.hexdigest()


def main():
    """Check every expected file and print a clear result."""
    print("Checking data in:", DATA_FOLDER)
    all_ok = True

    for file_name in EXPECTED_CHECKSUMS:
        file_path = os.path.join(DATA_FOLDER, file_name)
        expected = EXPECTED_CHECKSUMS[file_name]

        # Case 1: the file is missing.
        if not os.path.exists(file_path):
            print("  MISSING :", file_name)
            all_ok = False
            continue

        # Case 2: the file exists, so compare fingerprints.
        actual = sha256_of_file(file_path)
        if actual == expected:
            print("  OK      :", file_name)
        else:
            print("  CHANGED :", file_name)
            print("            expected", expected)
            print("            found   ", actual)
            all_ok = False

    if all_ok:
        print("Result: your data matches the original dataset.")
    else:
        print("Result: your data does NOT match. See data/README.md to download it again.")
        sys.exit(1)   # exit code 1 tells other tools that something went wrong


# This line means: only run main() when the file is run directly,
# not when another file imports it.
if __name__ == "__main__":
    main()
