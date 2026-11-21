import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

LIVE_URL = "https://danielhsu329.github.io/Danielhsu--Morning--brief/"
DEFAULT_DOWNLOAD_DIR = Path(r"D:\Users勿刪\User\Downloads")


def extract_report_date(filename_stem: str) -> str:
    """從檔名（如 2026_11_21 或 2026_11_21 (1)）自動擷取 YYYYMMDD，找不到則用今天日期。"""
    match = re.search(r"(20\d{2})[_-]?(\d{2})[_-]?(\d{2})", filename_stem)
    if match:
        return "".join(match.groups())
    return datetime.now().strftime("%Y%m%d")


def find_latest_brief(download_dir: Path = DEFAULT_DOWNLOAD_DIR) -> Path:
    """自動找出下載資料夾中最新匯出的 YYYY_MM_DD*.html 檔案。"""
    candidates = sorted(
        download_dir.glob("20??_??_??*.html"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(f"在 {download_dir} 找不到符合 YYYY_MM_DD.html 格式的晨報檔案")
    return candidates[-1]


def publish_dashboard(
    source_html_path: str | Path,
    repo_dir: str = r"C:\morning_brief_web",
    report_date: str | None = None,
) -> str:
    src = Path(source_html_path)
    if not src.exists():
        raise FileNotFoundError(f"找不到來源 HTML 檔案：{src}")

    repo = Path(repo_dir)
    archive_dir = repo / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    date_str = report_date or extract_report_date(src.stem)
    print(f"[讀取檔案] {src.name}（對應日期：{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}）")

    # 1. 覆蓋根目錄 index.html（主網址永遠顯示最新晨報）
    shutil.copy2(src, repo / "index.html")

    # 2. 留存當日歷史快照至 archive/YYYYMMDD.html
    shutil.copy2(src, archive_dir / f"{date_str}.html")

    # 3. 重新生成 archive/index.html 歷史列表
    files = sorted(archive_dir.glob("20*.html"), reverse=True)
    links = "\n".join(
        f'<li><a href="{f.name}">{f.stem[:4]}/{f.stem[4:6]}/{f.stem[6:]} 全球宏觀與產業策略晨報</a></li>'
        for f in files
    )
    archive_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>晨報歷史存檔 | Daniel Hsu</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 720px; margin: 48px auto; padding: 0 20px; line-height: 1.8; color: #1e293b; }}
  h2 {{ border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
  a {{ color: #2563eb; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <h2>全球宏觀與產業策略晨報 — 歷史存檔</h2>
  <p><a href="../">← 返回最新一期晨報</a></p>
  <ul>{links}</ul>
</body>
</html>"""
    (archive_dir / "index.html").write_text(archive_html, encoding="utf-8")

    # 4. Git 自動提交與推送
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)

    if status.stdout.strip():
        subprocess.run(["git", "commit", "-m", f"Publish brief {date_str}"], cwd=repo, check=True)
        subprocess.run(["git", "push"], cwd=repo, check=True)
        print(f"[發布成功] 最新晨報已上線：{LIVE_URL}")
        print(f"[歷史備份] {LIVE_URL}archive/{date_str}.html")
    else:
        print("[略過推送] 晨報內容與前一版相同，無需更新。")

    return LIVE_URL


if __name__ == "__main__":
    target_html = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_brief()
    publish_dashboard(source_html_path=target_html)