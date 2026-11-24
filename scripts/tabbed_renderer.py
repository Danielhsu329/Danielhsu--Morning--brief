"""Adapter for the original 11/24 six-tab layout; writes only a new edition."""
import html
import re

TABS=("macro","uscf","tw","aisc","energy","scen")
MARKER="<!-- BRIEF_TAB_RENDER_V1 -->"
CAPTIONS={"OPEC+ 11/29 會議":"供給與政策","洋山溢價 $500/噸":"現貨與期貨",
          "$325/MW-日上限":"容量市場","機構現金 3.6%":"情緒與現金"}
PLAIN={
 "c","d","a.close","a.daily_chg","a.category","a.name","a.range_note || '-'","a.note || '-'",
 "m.region","m.period","m.indicator","m.actual","m.prior_or_est","m.note",
 "c.ticker","c.period","c.alert || '-'","c.name","c.oct_rev_yoy","c.q3_gm_pct","c.q3_opm_pct","c.comment",
 "sf.note || '無額外備註。'","s.id","s.signal","s.status","s.latest","s.target_gate",
 "s.rank","s.segment","s.timing","s.falsification","c.body || '未取得／Unclear'",
 "s.name","active.name","active.label","active.key_assumptions","active.trigger","ev.date","ev.event","ev.threshold",
 "s.probability_pct","active.probability_pct","c.fcf_to_cfo_pct !== null ? c.fcf_to_cfo_pct + '%' : '-'",
 "alloc.cash_short_bond_pct ?? 0","alloc.defensive_equity_pct ?? 0","alloc.quality_ai_hardware_pct ?? 0","alloc.commodities_intl_pct ?? 0",
 "prefix","val","suffix","item"
}
ESC="""    function briefHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
"""

def is_tabbed(source, example):
    return all(f'id="tab-{t}"' in source and f'data-tab="tab-{t}"' in source for t in TABS) and all(
        f'id="{x}"' in source for x in ("moduleTabs","badgeDate","badgeCutoff","tradeDatesMeta","dataBoundaryText","headerTitle")) and bool({"data_boundary_note","key_events_boundary"} & example.get("meta",{}).keys())

def change_once(content, expression, replacement):
    matches=list(re.finditer(expression,content))
    if len(matches)!=1: raise ValueError("tab renderer anchor changed")
    m=matches[0]
    return content[:m.start()]+replacement(m)+content[m.end():]

def render(prefix, payload, suffix, new, archive):
    day=new["date"]
    y,m,d=map(int,day.split("-"))
    title=f"全球宏觀與產業策略晨報｜{y} 年 {m} 月 {d} 日"
    prefix=change_once(prefix,r"<title>[^<]*</title>",lambda _:f"<title>{title}</title>")
    for ident,value in (("headerTitle",title),("badgeDate",day),("badgeCutoff",new["cutoff_taipei"])):
        prefix=change_once(prefix,rf'(id="{ident}"[^>]*>)[^<]*',lambda x:x[1]+html.escape(value))
    prefix=change_once(prefix,r'(id="resetJsonBtn"[^>]*>)[^<]*',lambda m:m[1]+"重設為本期預設")
    prefix=re.sub(r"EMBEDDED DEFAULT_DATA \(\d{4}-\d{2}-\d{2}[^\n)]*\)","EMBEDDED DEFAULT_DATA (six-tab schema)",prefix)
    prefix=prefix.replace("（單位：億美元）","（單位：十億美元）").replace("（單位：新台幣億元）","（單位：新台幣十億元）")
    prefix=prefix.replace("美銀 11 月 FMS","美銀 FMS")
    prefix=prefix.replace("Q3 毛利率","季度毛利率").replace("Q3 GM / OPM","季度 GM / OPM").replace("Q3 CFO / CapEx / FCF","季度 CFO / CapEx / FCF")
    link = r'(<a\b[^>]*\bhref=")\./archive/("[^>]*>[^<]*歷史存檔[^<]*</a>)'
    if not re.search(link,prefix):
        prefix=change_once(prefix,r'(</footer>)',lambda m:
            '<nav aria-label="晨報存檔" class="max-w-[1560px] mx-auto px-4 py-2 text-xs"><a href="./archive/">歷史存檔</a></nav>'+m[1])
    if MARKER not in prefix:
        prefix=change_once(prefix,r"<!-- Footer -->",lambda m:MARKER+"\n  "+m[0])
        suffix=change_once(suffix,r"    function nullBadge\(\)",lambda m:ESC+"\n"+m[0])
        suffix=re.sub(r"\$\{([^{}]+)\}",lambda m:"$"+"{briefHtml("+m[1]+")}" if m[1] in PLAIN else m[0],suffix)
        suffix=suffix.replace("($億)","($十億)").replace(" + ' 億'"," + ' 十億'").replace(" (億)"," (十億新台幣)").replace("'', '億'","'', '十億元'")
        suffix=suffix.replace("自營商避險賣壓","自營商避險淨買賣").replace("台指期夜盤收盤 (歸屬 11/24)","台指期夜盤最後成交（非結算）")
        suffix=suffix.replace("美銀 11 月 FMS","美銀 FMS").replace("Q3 毛利率","季度毛利率").replace("Q3 營益率","季度營益率")
        for old,other in CAPTIONS.items(): suffix=suffix.replace(old,other)
        suffix=re.sub(r"meta\.date \|\| '\d{4}-\d{2}-\d{2}'","meta.date || DEFAULT_DATA.meta.date",suffix)
        suffix=re.sub(r"已重設為 \d{4}-\d{2}-\d{2} 預設資料","已重設為本期預設資料",suffix)
    if archive:
        prefix=change_once(prefix,link,lambda m:m[1]+"./"+m[2]+' <a class="text-sky-300" href="../">返回最新一期</a>')
    return prefix+"const DEFAULT_DATA = "+payload+suffix
