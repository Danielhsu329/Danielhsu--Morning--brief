"""11:36 browser layout migration: one sealed embedded data path, no client fetch."""
import json
import re
from datetime import date
from html import escape
from tabbed_renderer import change_once, ESC

BOUNDARY='    // 2. APPLICATION STATE & CHART INSTANCES'
LOADER='    // 6. DYNAMIC GITHUB PAGES FETCH'
MARKER='<!-- BRIEF_STATIC_1136 -->'

def identify(source):
    return MARKER in source or all(x in source for x in (BOUNDARY,LOADER,'id="eventBoundaryList"','id="assetCountBadge"'))

def split_manual(prefix,body):
    # The only extension allowed over strict JSON is ASCII unquoted object keys.
    tail_anchor=re.search(r'\n    };(?=\s*// ={10,}\s*// 2\. APPLICATION STATE)',body)
    if not tail_anchor: raise ValueError("11:36 manual object boundary changed")
    end=tail_anchor.start()+len('\n    }')
    data=re.sub(r'"(?:\\.|[^"\\])*"|(?P<key>\b[A-Za-z_][A-Za-z_0-9]*)(?=\s*:)',
                lambda m:json.dumps(m['key']) if m['key'] else m[0],body[:end])
    return prefix,data,body[end:]

def render(prefix,payload,suffix,metadata,archive):
    day=metadata["date"]
    dt=date.fromisoformat(day)
    title=f"全球宏觀與產業策略晨報｜{dt.year} 年 {dt.month} 月 {dt.day} 日"
    prefix=change_once(prefix,r"<title>[^<]*</title>",lambda _:f"<title>{title}</title>")
    for key,value in (("headerTitle",title),("badgeDate",day),("badgeCutoff",metadata["cutoff_taipei"]),
                      ("badgeTradeDates",f'美股 {metadata["us_trade_date"]} · 台股 {metadata["tw_trade_date"]} · 夜盤歸屬 {metadata["night_futures_official_date"] or "-"}')):
        prefix=change_once(prefix,rf'(id="{key}"[^>]*>)[^<]*',lambda m:m[1]+escape(value))
    prefix=change_once(prefix,r'(<option value=")\d{4}-\d{2}-\d{2}("[^>]*>)\d{4}-\d{2}-\d{2}',
                       lambda m:m[1]+day+m[2]+day)
    if MARKER not in prefix:
        prefix=prefix.replace("<!-- Application Logic -->",MARKER+"\n  <!-- Application Logic -->")
        prefix=re.sub(r'BUILT-IN DEFAULT DATA \([^\n)]*\)','SEALED EMBEDDED DATA',prefix)
        prefix=prefix.replace("10 月營收","月營收").replace('重新同步 GitHub','重新載入本期')
        # Disable the manual JSON import control entirely for generated pages.
        prefix=prefix.replace('id="applyJsonBtn"','id="applyJsonBtn" disabled hidden aria-hidden="true"')
        prefix=re.sub(r'title="重新同步[^"]*"','title="重新載入本期"',prefix)
        suffix=change_once(suffix,r"    function formatNullable\(",lambda m:ESC+"\n"+m[0])
        a=suffix.index('    document.getElementById("applyJsonBtn").addEventListener')
        b=suffix.index(LOADER,a)
        suffix=suffix[:a]+suffix[b:]
        a=suffix.index(LOADER)
        suffix=suffix[:a]+'''    // One sealed edition; history opens immutable HTML files, not a second feed.
    function initDashboard() {
      renderAll(JSON.parse(JSON.stringify(DEFAULT_DATA)));
      setSyncStatus("embedded", "本期封存資料");
      const picker = document.getElementById("history-date-select");
      picker.textContent = "";
      const option = new Option(DEFAULT_DATA.meta.date, DEFAULT_DATA.meta.date);
      picker.add(option);
      picker.disabled = true;
      document.getElementById("prevDateBtn").disabled = true;
      document.getElementById("nextDateBtn").disabled = true;
    }
    document.getElementById("refreshDataBtn").addEventListener("click", initDashboard);
    window.addEventListener("DOMContentLoaded", initDashboard);
  </script>
</body>
</html>
'''
        # Human-facing units are distinct from physical units in data.
        suffix=re.sub(r'(val: sf\.\w+_twd_bn, unit:) " 億"',r'\1 " 十億元"',suffix)
        suffix=suffix.replace('台指期夜盤收盤 (11/24)','台指期夜盤最後成交（非結算）')
        suffix=suffix.replace('(${c.oct_rev_yoy})', '${c.oct_rev_yoy == null ? "-" : briefHtml(c.oct_rev_yoy)}')
        suffix=re.sub(r'\$\{((?:item|cat|d|val|suffix|\w+\.\w+(?: \|\| "-")?))\}',
                      lambda m:'${briefHtml('+m[1]+')}',suffix)
    link=r'(<a\b[^>]*\bhref=")\./archive/("[^>]*>[^<]*歷史存檔[^<]*</a>)'
    if archive:
        prefix=change_once(prefix,link,lambda m:m[1]+"./"+m[2]+' <a href="../">回到最新一期</a>')
    return prefix+"const DEFAULT_DATA = "+payload+suffix
