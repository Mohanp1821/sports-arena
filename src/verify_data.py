"""
verify_data.py - Step 1: check the data files are the original ones.

Each file's SHA-256 checksum (a fingerprint of every byte) is compared with
the value recorded when the project was built. One changed byte = a new fingerprint.

Run:  python src/verify_data.py
"""

import hashlib
import os
import sys

DATA_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Fingerprints recorded when the project was built (also listed in data/README.md).
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
    """The SHA-256 fingerprint of a file, read 1 MB at a time so big files fit in memory."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as file:
        while True:
            piece = file.read(1024 * 1024)
            if not piece:
                break
            hasher.update(piece)
    return hasher.hexdigest()


def main():
    print("Checking data in:", DATA_FOLDER)
    all_ok = True
    for file_name, expected in EXPECTED_CHECKSUMS.items():
        file_path = os.path.join(DATA_FOLDER, file_name)
        if not os.path.exists(file_path):
            print("  MISSING :", file_name)
            all_ok = False
        elif sha256_of_file(file_path) == expected:
            print("  OK      :", file_name)
        else:
            print("  CHANGED :", file_name)
            all_ok = False

    if all_ok:
        print("Result: your data matches the original dataset.")
    else:
        print("Result: your data does NOT match. See data/README.md to download it again.")
        sys.exit(1)   # a non-zero exit stops run_all.sh and Docker


if __name__ == "__main__":
    main()
