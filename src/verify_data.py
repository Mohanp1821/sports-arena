"""
verify_data.py
--------------
Step 1 of the Sports Arena pipeline.

This script checks that the raw dataset on your computer is EXACTLY the same
as the one the project was built with. It does this using a SHA-256 checksum.

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
RAW_FOLDER = os.path.join(PROJECT_FOLDER, "data", "raw")

# The fingerprints we recorded when the project was built.
# These same values are written in data/README.md.
EXPECTED_CHECKSUMS = {
    "matches.csv": "57241c8438ce93f1824e8a07f779dc1c588687cc8afa344b2974518ad35195cb",
    "deliveries.csv": "412dca480d2bfd89138828331d45d687c29d7fb402f6b002803dd16952107314",
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
    print("Checking raw data in:", RAW_FOLDER)
    all_ok = True

    for file_name in EXPECTED_CHECKSUMS:
        file_path = os.path.join(RAW_FOLDER, file_name)
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
