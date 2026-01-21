import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent

def run(name: str):
    p = subprocess.run([sys.executable, str(HERE / name)], check=True)
    return p.returncode

if __name__ == "__main__":
    run("build_dataset_v2.py")
    run("make_splits_v2.py")
    run("make_test_hard.py")
    print("DONE ✅")
