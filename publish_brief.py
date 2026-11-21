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


def inject_nav_bar(raw_html: str, date_str: str, is_archive: bool = False) -> str:
    """在 <body> 開頭插入不遮擋版面的吸頂導覽列（支援重複執行覆蓋更新）。"""
    # 若檔案已含舊導覽列則先清除，確保重複執行不會疊加
    cleaned_html = re.sub(
        r"<!-- ARES_NAV_START -->.*?<!-- ARES_NAV_END -->\s*",
        "",
        raw_html,
        flags=re.DOTALL,
    )

    formatted_date = f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
    publish_time = datetime.now().strftime("%H:%M")

    if is_archive:
        badge_bg = "#78350f"
        badge_fg = "#fde68a"
        badge_text = "歷史存檔"
        status_text = f"檢視日期：{formatted_date}"
        actions_html = (
            '<a href="./" class="ares-nav-btn ares-nav-secondary">歷史存檔目錄</a>'
            '<a href="../" class="ares-nav-btn ares-nav-primary">返回最新一期 →</a>'
        )
    else:
        badge_bg = "#064e3b"
        badge_fg = "#6ee7b7"
        badge_text = "最新一期"
        status_text = f"{formatted_date} 晨報（更新於 {publish_time}）"
        actions_html = (
            '<a href="archive/" class="ares-nav-btn ares-nav-primary">歷史存檔目錄 →</a>'
        )

    nav_block = f"""<!-- ARES_NAV_START -->
<style>
  #ares-brief-nav {{
    position: sticky;
    top: 0;
    z-index: 99999;
    width: 100%;
    box-sizing: border-box;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px 20px;
    background: rgba(15, 23, 42, 0.96);
    backdrop-filter: blur(8px);
    color: #f1f5f9;
    border-bottom: 1px solid #334155;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif;
    font-size: 13px;
    line-height: 1.4;
  }}
  #ares-brief-nav .ares-nav-left {{
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  #ares-brief-nav .ares-nav-badge {{
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: {badge_bg};
    color: {badge_fg};
  }}
  #ares-brief-nav .ares-nav-actions {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  #ares-brief-nav .ares-nav-btn {{
    display: inline-block;
    padding: 4px 12px;
    border-radius: 5px;
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    transition: background 0.15s ease;
  }}
  #ares-brief-nav .ares-nav-primary {{
    background: #2563eb;
    color: #ffffff;
  }}
  #ares-brief-nav .ares-nav-primary:hover {{
    background: #1d4ed8;
  }}
  #ares-brief-nav .ares-nav-secondary {{
    background: #1e293b;
    color: #cbd5e1;
    border: 1px solid #475569;
  }}
  #ares-brief-nav .ares-nav-secondary:hover {{
    background: #334155;
    color: #ffffff;
  }}
  @media print {{
    #ares-brief-nav {{ display: none !important; }}
  }}
</style>
<div id="ares-brief-nav">
  <div class="ares-nav-left">
    <span class="ares-nav-badge">{badge_text}</span>
    <span>{status_text}</span>
  </div>
  <div class="ares-nav-actions">
    {actions_html}
  </div>
</div>
<!-- ARES_NAV_END -->"""

    if re.search(r"<body[^>]*>", cleaned_html, flags=re.IGNORECASE):
        return re.sub(
            r"<body[^>]*>",
            lambda m: f"{m.group(0)}\n{nav_block}",
            cleaned_html,
            count=1,
            flags=re.IGNORECASE,
        )
    return f"{nav_block}\n{cleaned_html}"


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

    raw_html = src.read_text(encoding="utf-8")

    # 1. 生成含「歷史存檔目錄 →」按鈕的首頁 index.html
    latest_html = inject_nav_bar(raw_html, date_str, is_archive=False)
    (repo / "index.html").write_text(latest_html, encoding="utf-8")

    # 2. 生成含「返回最新一期 →」按鈕的歷史快照 archive/YYYYMMDD.html
    archived_html = inject_nav_bar(raw_html, date_str, is_archive=True)
    (archive_dir / f"{date_str}.html").write_text(archived_html, encoding="utf-8")

    # 3. 重新生成 archive/index.html 歷史列表（深色極簡風格與導覽列一致）
    files = sorted(archive_dir.glob("20*.html"), reverse=True)
    links = "\n".join(
        f'<li><a href="{f.name}"><span class="date">{f.stem[:4]}/{f.stem[4:6]}/{f.stem[6:]}</span> 全球宏觀與產業策略晨報</a></li>'
        for f in files
    )
    archive_index_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>晨報歷史存檔 | Daniel Hsu</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft JhengHei", sans-serif; background: #0f172a; color: #e2e8f0; max-width: 720px; margin: 48px auto; padding: 0 20px; line-height: 1.8; }}
  h2 {{ border-bottom: 1px solid #334155; padding-bottom: 12px; color: #f8fafc; }}
  .back-btn {{ display: inline-block; margin-bottom: 16px; padding: 6px 14px; background: #2563eb; color: #fff; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 600; }}
  .back-btn:hover {{ background: #1d4ed8; }}
  ul {{ list-style: none; padding: 0; }}
  li {{ border-bottom: 1px solid #1e293b; }}
  li a {{ display: block; padding: 12px 8px; color: #93c5fd; text-decoration: none; }}
  li a:hover {{ background: #1e293b; color: #ffffff; border-radius: 6px; }}
  .date {{ font-family: monospace; color: #94a3b8; margin-right: 12px; }}
</style>
</head>
<body>
  <h2>全球宏觀與產業策略晨報 — 歷史存檔</h2>
  <a href="../" class="back-btn">← 返回最新一期晨報</a>
  <ul>{links}</ul>
</body>
</html>"""
    (archive_dir / "index.html").write_text(archive_index_html, encoding="utf-8")

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