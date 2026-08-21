from pathlib import Path

Path("result.txt").write_text("artifact created\n", encoding="utf-8")
print("artifact=result.txt")
