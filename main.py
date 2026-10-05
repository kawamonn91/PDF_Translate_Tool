import sys

from ja_translator.gui import run


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--diagnose":
        from ja_translator.diagnose import run as diagnose

        sys.exit(diagnose(sys.argv[2]))
    sys.exit(run())
