# %% [markdown]
# # データサイエンス ニュースダイジェスト(国内のみ・毎朝自動実行版)
# 国内RSSを集めて index.html / ds_news_digest.md に出力する。
# 標準ライブラリだけで動く(追加インストール・APIキーは不要)。

# %% 設定(定数はここに集約)
DOMESTIC_FEEDS = {
    "Qiita(機械学習)": "https://qiita.com/tags/machinelearning/feed",
    "Qiita(データサイエンス)": "https://qiita.com/tags/データサイエンス/feed",
    "Zenn(機械学習)": "https://zenn.dev/topics/machinelearning/feed",
    "ITmedia AI+": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
    "はてなブックマーク(IT)": "https://b.hatena.ne.jp/hotentry/it.rss",
}
# 一般ニュース系のフィードは、キーワードで絞り込む
FILTER_FEEDS = {"ITmedia AI+", "はてなブックマーク(IT)"}
KEYWORDS = [
    "データサイエンス", "機械学習", "深層学習", "ディープラーニング", "生成ai", "llm",
    "データ分析", "統計", "python", "kaggle", "強化学習", "ai",
]

MAX_PER_FEED = 8        # フィードごとの最大件数
DAYS_BACK = 7           # 何日前までの記事を対象にするか
SUMMARY_CHARS = 200     # 要約として使う最大文字数
TIMEOUT_SEC = 15
USER_AGENT = "Mozilla/5.0 (ds-news-digest)"
OUTPUT_HTML_NAME = "index.html"
OUTPUT_MD_NAME = "ds_news_digest.md"

# %% インポート
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

try:
    BASE_DIR = Path(__file__).resolve().parent  # タスクスケジューラ実行でも保存先がぶれない
except NameError:
    BASE_DIR = Path.cwd()  # セル実行(Jupyter等)の場合


# %% RSS / Atom の取得とパース
def local_name(el):
    """名前空間を除いたタグ名を返す。"""
    return el.tag.rsplit("}", 1)[-1]


def child_text(el, *names):
    for c in el:
        if local_name(c) in names and (c.text or "").strip():
            return c.text.strip()
    return ""


def child_link(el):
    for c in el:
        if local_name(c) == "link":
            href = c.get("href") or (c.text or "").strip()
            if href:
                return href
    return ""


def clean_text(s, limit=None):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", html.unescape(s)).strip()
    if limit and len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s


def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)  # RSS 2.0 形式
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))  # Atom / RSS 1.0
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def fetch_entries(source, url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as r:
        root = ET.fromstring(r.read())
    entries = []
    for el in root.iter():
        if local_name(el) not in ("item", "entry"):
            continue
        entries.append({
            "source": source,
            "title": clean_text(child_text(el, "title")),
            "link": child_link(el),
            "summary": clean_text(
                child_text(el, "description", "summary", "content", "encoded"), SUMMARY_CHARS
            ),
            "date": parse_date(child_text(el, "pubDate", "published", "updated", "date")),
        })
    return entries


def collect(feeds, filter_sources=frozenset()):
    since = datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
    results = []
    for source, url in feeds.items():
        print(f"取得中: {source}")
        try:
            entries = fetch_entries(source, url)
        except Exception as e:
            print(f"[skip] {source}: {e}")
            continue
        picked = []
        for e in entries:
            if e["date"] and e["date"] < since:
                continue
            if source in filter_sources:
                text = (e["title"] + " " + e["summary"]).lower()
                if not any(k in text for k in KEYWORDS):
                    continue
            picked.append(e)
        picked.sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        results.extend(picked[:MAX_PER_FEED])
    # 全体を新しい順に並べる
    results.sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return results


# %% 出力(Markdown / HTML)
def fmt_date(d):
    return d.astimezone().strftime("%Y-%m-%d") if d else "日付不明"


def render_md(entries, now):
    lines = [f"# データサイエンス ニュースダイジェスト ({now:%Y-%m-%d})", ""]
    for e in entries:
        lines.append(f"- [{e['title']}]({e['link']}) — {e['source']} / {fmt_date(e['date'])}")
        if e["summary"]:
            lines.append(f"  - {e['summary']}")
    return "\n".join(lines) + "\n"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>データサイエンス ニュース</title>
<style>
:root {{ --bg:#000; --card:#0f0f10; --text:#ececec; --sub:#8a8f98; --accent:#6ea8ff; --line:#222428; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text);
  font-family:"Hiragino Sans","Yu Gothic UI","Meiryo",system-ui,sans-serif; line-height:1.7; }}
main {{ max-width:860px; margin:0 auto; padding:28px 16px 56px; }}
h1 {{ font-size:1.4rem; margin:0 0 4px; letter-spacing:.02em; }}
.updated {{ color:var(--sub); font-size:.85rem; margin-bottom:24px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px; margin-bottom:10px; transition:border-color .15s; }}
.card:hover {{ border-color:var(--accent); }}
.card a {{ color:var(--accent); font-weight:600; text-decoration:none; }}
.card a:hover {{ text-decoration:underline; }}
.meta {{ color:var(--sub); font-size:.8rem; margin-top:2px; }}
.sum {{ margin:6px 0 0; font-size:.92rem; color:#c9ccd1; }}
.empty {{ color:var(--sub); }}
</style>
</head>
<body>
<main>
<h1>データサイエンス ニュース</h1>
<div class="updated">最終更新: {updated} / {count} 件</div>
{cards}
</main>
</body>
</html>
"""


def card(e):
    esc = html.escape
    parts = [
        '<div class="card">',
        f'<a href="{esc(e["link"], quote=True)}" target="_blank" rel="noopener">{esc(e["title"])}</a>',
        f'<div class="meta">{esc(e["source"])} / {fmt_date(e["date"])}</div>',
    ]
    if e["summary"]:
        parts.append(f'<p class="sum">{esc(e["summary"])}</p>')
    parts.append("</div>")
    return "\n".join(parts)


def render_html(entries, now):
    cards = "\n".join(card(e) for e in entries) or '<p class="empty">該当記事がありません</p>'
    return HTML_TEMPLATE.format(updated=f"{now:%Y-%m-%d %H:%M}", count=len(entries), cards=cards)


# %% 実行
def main():
    entries = collect(DOMESTIC_FEEDS, FILTER_FEEDS)

    if not entries:
        # ネット未接続などで1件も取れない場合、前回のHTMLを空で上書きしない
        print("記事が1件も取得できなかったため、出力を更新しませんでした。")
        raise SystemExit(1)

    now = datetime.now()
    (BASE_DIR / OUTPUT_HTML_NAME).write_text(render_html(entries, now), encoding="utf-8")
    (BASE_DIR / OUTPUT_MD_NAME).write_text(render_md(entries, now), encoding="utf-8")
    print(f"保存しました: {BASE_DIR / OUTPUT_HTML_NAME}  ({len(entries)} 件)")


if __name__ == "__main__":
    main()