from flask import Flask, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import Flowable
import io, re

app = Flask(__name__)

# ── Brand palette ──────────────────────────────────────────────────
SAGE_GREEN  = colors.HexColor("#516E4F")
SAGE_DARK   = colors.HexColor("#3A5238")
SAGE_MID    = colors.HexColor("#426040")
SAGE_PALE   = colors.HexColor("#C8D9C7")
SAGE_LIGHT  = colors.HexColor("#E8F0E7")
CREAM       = colors.HexColor("#FCFAED")
CREAM_DARK  = colors.HexColor("#F0EDD8")
ACCENT_GOLD = colors.HexColor("#C9A84C")
TEXT_DARK   = colors.HexColor("#2C2C2C")
TEXT_MID    = colors.HexColor("#555555")
TEXT_LIGHT  = colors.HexColor("#888888")
WHITE       = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
COL_W  = PAGE_W - 2 * MARGIN


# ── Custom Flowable: BarChart ──────────────────────────────────────
class BarChart(Flowable):
    def __init__(self, posts, width, height=140):
        super().__init__()
        self.posts = posts
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        if not self.posts:
            return
        max_val = max(p["value"] for p in self.posts) or 1
        bar_h = min(18, (self.height - 10) / max(len(self.posts), 1) - 3)
        label_w = 72
        bar_area = self.width - label_w - 36
        type_colors = {
            "FEED": SAGE_GREEN, "REEL": SAGE_DARK,
            "CAROUSEL_ALBUM": ACCENT_GOLD, "IMAGE": SAGE_MID,
            "VIDEO": colors.HexColor("#6B8F69"),
        }
        for i, post in enumerate(self.posts):
            y = self.height - 10 - i * (bar_h + 3)
            bar_len = (post["value"] / max_val) * bar_area
            ptype = post.get("type", "FEED").upper()
            bar_color = type_colors.get(ptype, SAGE_GREEN)
            c.setFillColor(TEXT_MID)
            c.setFont("Helvetica", 6.5)
            c.drawRightString(label_w - 4, y + bar_h * 0.3, str(post["label"])[:13])
            c.setFillColor(SAGE_LIGHT)
            c.roundRect(label_w, y, bar_area, bar_h, 2, fill=1, stroke=0)
            if bar_len > 0:
                c.setFillColor(bar_color)
                c.roundRect(label_w, y, bar_len, bar_h, 2, fill=1, stroke=0)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(label_w + bar_len + 4, y + bar_h * 0.3, str(post["value"]))


# ── Helpers ─────────────────────────────────────────────────────────
def bold(text):
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', str(text))

def fmt(val):
    try:
        s = str(val).replace(',', '').replace('%', '')
        n = float(s)
        if n >= 1000: return f"{n:,.0f}"
        if '%' in str(val): return str(val)
        return str(val)
    except:
        return str(val)

def safe_pct(a, b):
    try:
        return f"{float(str(a).replace(',','')) / float(str(b).replace(',','')) * 100:.2f}%"
    except:
        return "—"

def parse_posts(raw):
    posts = []
    if not raw:
        return posts
    for line in str(raw).split('\n'):
        line = line.strip()
        if not line:
            continue
        post = {}
        for part in line.split('|'):
            part = part.strip()
            if ':' in part:
                k, v = part.split(':', 1)
                post[k.strip().lower()] = v.strip()
        if post:
            try:
                post['likes_int']    = int(post.get('likes', 0))
                post['comments_int'] = int(post.get('comments', 0))
                post['eng_int']      = post['likes_int'] + post['comments_int']
            except:
                post['likes_int'] = post['comments_int'] = post['eng_int'] = 0
            posts.append(post)
    return sorted(posts, key=lambda x: x['eng_int'], reverse=True)


def parse_posts_json(raw):
    """Parse posts_data JSON array sent from Make.com Array Aggregator."""
    import json, re
    posts = []
    if not raw:
        return posts
    try:
        # Replace literal newlines/tabs inside the JSON string (from Instagram captions)
        raw_clean = re.sub(r'[\r\n\t]+', ' ', str(raw))
        items = json.loads(raw_clean)
        if not isinstance(items, list):
            return posts
        for item in items:
            post = {
                'date':     str(item.get('date', '—')),
                'type':     str(item.get('media_type', 'IMAGE')),
                'likes':    str(item.get('likes', '0')),
                'comments': str(item.get('comments', '0')),
                'url':      str(item.get('permalink', '')),
                'caption':  str(item.get('caption', '')),
                'post_id':  str(item.get('post_id', '')),
            }
            try:
                post['likes_int']    = int(float(str(item.get('likes', 0))))
                post['comments_int'] = int(float(str(item.get('comments', 0))))
                post['eng_int']      = post['likes_int'] + post['comments_int']
            except:
                post['likes_int'] = post['comments_int'] = post['eng_int'] = 0
            posts.append(post)
        return sorted(posts, key=lambda x: x['eng_int'], reverse=True)
    except:
        return posts


# ── Style dictionary ────────────────────────────────────────────────
def make_styles():
    return {
        # Cover
        "cover_tag":   ParagraphStyle("cover_tag",   fontSize=9,  textColor=ACCENT_GOLD, fontName="Helvetica-Bold", leading=12, spaceAfter=10),
        "cover_title": ParagraphStyle("cover_title", fontSize=34, textColor=CREAM,       fontName="Helvetica-Bold", leading=40, spaceAfter=6),
        "cover_sub":   ParagraphStyle("cover_sub",   fontSize=14, textColor=SAGE_PALE,   fontName="Helvetica",      leading=20, spaceAfter=4),
        "meta_k":      ParagraphStyle("meta_k",      fontSize=7.5, textColor=SAGE_PALE,  fontName="Helvetica-Bold", leading=11),
        "meta_v":      ParagraphStyle("meta_v",      fontSize=9,   textColor=CREAM,      fontName="Helvetica",      leading=13),
        # Section
        "h1":          ParagraphStyle("h1",  fontSize=15, textColor=SAGE_DARK, fontName="Helvetica-Bold", leading=19, spaceBefore=6, spaceAfter=3),
        "h2":          ParagraphStyle("h2",  fontSize=11, textColor=SAGE_DARK, fontName="Helvetica-Bold", leading=15, spaceBefore=6, spaceAfter=3),
        "h3":          ParagraphStyle("h3",  fontSize=9.5, textColor=SAGE_MID,  fontName="Helvetica-Bold", leading=13, spaceBefore=4, spaceAfter=2),
        # Body
        "body":        ParagraphStyle("body",    fontSize=9.5, textColor=TEXT_DARK, fontName="Helvetica", leading=15, spaceAfter=4, alignment=TA_JUSTIFY),
        "body_sm":     ParagraphStyle("body_sm", fontSize=8.5, textColor=TEXT_MID,  fontName="Helvetica", leading=13, spaceAfter=3),
        "caption":     ParagraphStyle("caption", fontSize=7.5, textColor=TEXT_LIGHT,fontName="Helvetica", leading=10, alignment=TA_CENTER),
        "bullet":      ParagraphStyle("bullet",  fontSize=9.5, textColor=TEXT_DARK, fontName="Helvetica", leading=15, leftIndent=14, firstLineIndent=-14, spaceAfter=4),
        # KPI
        "kpi_big":     ParagraphStyle("kpi_big",   fontSize=22, textColor=SAGE_DARK, fontName="Helvetica-Bold", leading=26),
        "kpi_label":   ParagraphStyle("kpi_label", fontSize=7.5, textColor=TEXT_LIGHT, fontName="Helvetica", leading=10),
        # Table
        "th":          ParagraphStyle("th",      fontSize=7.5, textColor=CREAM,     fontName="Helvetica-Bold", leading=10, alignment=TA_CENTER),
        "td":          ParagraphStyle("td",      fontSize=8,   textColor=TEXT_DARK, fontName="Helvetica",      leading=11, alignment=TA_CENTER),
        "td_left":     ParagraphStyle("td_left", fontSize=8,   textColor=TEXT_DARK, fontName="Helvetica",      leading=11, alignment=TA_LEFT),
        # Footer
        "footer_sm":   ParagraphStyle("footer_sm", fontSize=7.5, textColor=TEXT_LIGHT, fontName="Helvetica", leading=10, alignment=TA_CENTER),
        "disclaimer":  ParagraphStyle("disclaimer", fontSize=7.5, textColor=TEXT_LIGHT, fontName="Helvetica", leading=11, spaceAfter=3),
    }


# ── Page callbacks ───────────────────────────────────────────────────
page_num = [0]

def cover_bg(c, doc):
    page_num[0] = 1
    c.saveState()
    c.setFillColor(SAGE_DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(SAGE_MID)
    c.circle(PAGE_W + 10, PAGE_H * 0.72, 155, fill=1, stroke=0)
    c.setFillColor(SAGE_GREEN)
    c.circle(PAGE_W - 20, PAGE_H * 0.62, 95, fill=1, stroke=0)
    c.setFillColor(CREAM)
    c.rect(0, 0, PAGE_W, 26 * mm, fill=1, stroke=0)
    c.setFillColor(ACCENT_GOLD)
    c.rect(0, 26 * mm, PAGE_W, 2, fill=1, stroke=0)
    c.setFillColor(TEXT_MID)
    c.setFont("Helvetica", 7.5)
    c.drawString(MARGIN, 9 * mm, "sagemedia.in  |  Confidential  |  Not for public distribution")
    c.setFont("Helvetica-Bold", 8)
    c.drawRightString(PAGE_W - MARGIN, 9 * mm, "SAGE MEDIA")
    c.restoreState()


def page_bg(c, doc):
    page_num[0] += 1
    c.saveState()
    c.setFillColor(CREAM)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(SAGE_DARK)
    c.rect(0, 0, PAGE_W, 14 * mm, fill=1, stroke=0)
    c.setFillColor(SAGE_PALE)
    c.setFont("Helvetica", 7)
    c.drawString(MARGIN, 5 * mm, "Prepared by Sage Media  •  sagemedia.in  •  Confidential")
    c.drawRightString(PAGE_W - MARGIN, 5 * mm, f"Page {page_num[0]}")
    c.setFillColor(SAGE_GREEN)
    c.rect(0, PAGE_H - 3, PAGE_W, 3, fill=1, stroke=0)
    c.restoreState()


# ── Section builders ─────────────────────────────────────────────────

def sec_header(title, st):
    return [
        Paragraph(title.upper(), st["h1"]),
        HRFlowable(width=COL_W, thickness=2, color=SAGE_GREEN, spaceAfter=8),
    ]


def build_cover(data, st):
    story = [Spacer(1, 58 * mm)]
    story.append(Paragraph("INSTAGRAM PERFORMANCE REPORT", st["cover_tag"]))
    story.append(Paragraph(data.get("brand_name", "Brand"), st["cover_title"]))
    story.append(Paragraph(f"Reporting Period: <b>{data.get('month','—')}</b>", st["cover_sub"]))
    story.append(Spacer(1, 30 * mm))

    meta = [
        [Paragraph("PREPARED FOR", st["meta_k"]),
         Paragraph("PREPARED BY",  st["meta_k"]),
         Paragraph("ACCOUNT MANAGER", st["meta_k"])],
        [Paragraph(data.get("brand_name","—"), st["meta_v"]),
         Paragraph("Sage Media", st["meta_v"]),
         Paragraph(data.get("account_manager","—"), st["meta_v"])],
        [Paragraph("DATA PERIOD", st["meta_k"]),
         Paragraph("REPORT DATE",  st["meta_k"]),
         Paragraph("DATA SOURCE",  st["meta_k"])],
        [Paragraph("Last 28 Days", st["meta_v"]),
         Paragraph(data.get("report_date","—"), st["meta_v"]),
         Paragraph("Meta Business Suite", st["meta_v"])],
    ]
    cw = COL_W / 3
    mt = Table(meta, colWidths=[cw, cw, cw])
    mt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), colors.HexColor("#2E4530")),
        ("TOPPADDING",   (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LEFTPADDING",  (0,0),(-1,-1), 12),
        ("RIGHTPADDING", (0,0),(-1,-1), 12),
        ("LINEBELOW",    (0,1),(-1,1),  0.5, SAGE_GREEN),
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[colors.HexColor("#2E4530"),
                                          colors.HexColor("#364E38"),
                                          colors.HexColor("#2E4530"),
                                          colors.HexColor("#364E38")]),
    ]))
    story.append(mt)
    story.append(PageBreak())
    return story


def build_executive_summary(data, st):
    story = sec_header("01  |  Executive Summary", st)

    brand  = data.get("brand_name", "the brand")
    month  = data.get("month","this period")
    reach  = fmt(data.get("reach","—"))
    inter  = fmt(data.get("interactions","—"))
    eng    = fmt(data.get("accounts_engaged","—"))
    nf     = fmt(data.get("new_followers","—"))
    er     = data.get("eng_rate") or safe_pct(data.get("accounts_engaged","0"), data.get("reach","1"))

    story.append(Paragraph(
        f"This report presents a comprehensive analysis of <b>{brand}</b>'s Instagram performance "
        f"for <b>{month}</b>. All data is sourced from the Instagram Graph API via Meta Business Suite "
        f"and reflects the most recent 28-day rolling period. Metrics represent organic performance.",
        st["body"]))
    story.append(Spacer(1, 6))

    # 3 highlight stats
    highlights = [
        (reach, "Total Reach",       "Unique accounts reached"),
        (inter, "Total Interactions","Likes, comments & saves"),
        (er,    "Engagement Rate",   "Engaged ÷ Reach × 100"),
    ]
    cw = (COL_W - 8) / 3
    cells = [[
        [Paragraph(str(v), st["kpi_big"]),
         Paragraph(l.upper(), st["kpi_label"]),
         Spacer(1,2),
         Paragraph(d, ParagraphStyle("hd", fontSize=7.5, textColor=TEXT_LIGHT,
                                      fontName="Helvetica", leading=10))]
        for v, l, d in highlights
    ]]
    ht = Table(cells, colWidths=[cw]*3)
    ht.setStyle(TableStyle([
        ("BACKGROUND",      (0,0),(-1,-1), WHITE),
        ("LEFTPADDING",     (0,0),(-1,-1), 13),
        ("TOPPADDING",      (0,0),(-1,-1), 13),
        ("BOTTOMPADDING",   (0,0),(-1,-1), 13),
        ("RIGHTPADDING",    (0,0),(-1,-1), 13),
        ("LINEBEFORE",      (0,0),(-1,-1), 4, SAGE_GREEN),
        ("BOX",             (0,0),(-1,-1), 0.5, SAGE_PALE),
        ("LINEAFTER",       (0,0),(1,-1),  0.5, SAGE_PALE),
        ("COLBACKGROUNDS",  (0,0),(-1,-1), [WHITE, CREAM_DARK, WHITE]),
    ]))
    story.append(ht)
    story.append(Spacer(1, 10))

    # Key observations
    story.append(Paragraph("Key Observations", st["h2"]))
    story.append(Spacer(1, 3))
    try:
        r  = float(str(data.get("reach","0")).replace(",",""))
        ae = float(str(data.get("accounts_engaged","0")).replace(",",""))
        i  = float(str(data.get("interactions","0")).replace(",",""))
        pv = float(str(data.get("profile_views","0")).replace(",",""))
        wc = float(str(data.get("website_clicks","0")).replace(",",""))
        nf_ = float(str(data.get("new_followers","0")).replace(",",""))
        obs = [
            f"The account reached <b>{fmt(r)}</b> unique users — every impression connected with a distinct, real person.",
            f"Engagement rate stands at <b>{ae/r*100:.2f}%</b> ({fmt(ae)} accounts engaged of {fmt(r)} reached), a strong signal of content resonance.",
            f"<b>{fmt(i)}</b> total interactions recorded — averaging approximately <b>{i/28:.0f} interactions per day</b>.",
            f"<b>{fmt(pv)}</b> profile views indicate strong discovery intent — users actively seeking more information after seeing content.",
            f"<b>{fmt(wc)}</b> website clicks reflect conversion impact of the bio link and story CTAs.",
            f"{'Follower growth was flat this period — focus on conversion of engaged audience into followers.' if nf_==0 else f'<b>{fmt(nf_)}</b> net new followers gained — consistent brand momentum.'}",
        ]
    except:
        obs = ["Performance data is available in the metrics section below."]

    for o in obs:
        story.append(Paragraph(f"•  {bold(o)}", st["bullet"]))
    story.append(Spacer(1, 8))

    # Performance snapshot table
    story.append(Paragraph("Performance at a Glance", st["h2"]))
    story.append(Spacer(1, 4))
    try:
        r_  = float(str(data.get("reach","0")).replace(",",""))
        ae_ = float(str(data.get("accounts_engaged","0")).replace(",",""))
        er_val = ae_/r_*100 if r_ else 0
        er_tag = "Excellent" if er_val >= 3 else ("Good" if er_val >= 1 else ("Average" if er_val >= 0.5 else "Below avg"))
    except:
        er_tag = "—"
    snap = [
        [Paragraph("METRIC",st["th"]),Paragraph("VALUE",st["th"]),Paragraph("CONTEXT",st["th"]),Paragraph("NOTE",st["th"])],
        [Paragraph("Reach",st["td_left"]),Paragraph(fmt(data.get("reach","—")),st["td"]),Paragraph("Core awareness metric",st["td"]),Paragraph("Unique accounts",st["td"])],
        [Paragraph("Engagement Rate",st["td_left"]),Paragraph(er,st["td"]),Paragraph("1–3% typical for business",st["td"]),Paragraph(f"<b>{er_tag}</b>",st["td"])],
        [Paragraph("Interactions",st["td_left"]),Paragraph(fmt(data.get("interactions","—")),st["td"]),Paragraph("High = strong content",st["td"]),Paragraph("Likes + comments",st["td"])],
        [Paragraph("Profile Views",st["td_left"]),Paragraph(fmt(data.get("profile_views","—")),st["td"]),Paragraph("Discovery intent",st["td"]),Paragraph("Page visits",st["td"])],
        [Paragraph("Website Clicks",st["td_left"]),Paragraph(fmt(data.get("website_clicks","—")),st["td"]),Paragraph("Conversion signal",st["td"]),Paragraph("Bio/story link taps",st["td"])],
        [Paragraph("New Followers",st["td_left"]),Paragraph(fmt(data.get("new_followers","—")),st["td"]),Paragraph("Growth metric",st["td"]),Paragraph("Net gain",st["td"])],
        [Paragraph("Story Replies",st["td_left"]),Paragraph(fmt(data.get("story_replies","—")),st["td"]),Paragraph("Community signal",st["td"]),Paragraph("Direct engagement",st["td"])],
    ]
    cws = [COL_W*0.27,COL_W*0.15,COL_W*0.33,COL_W*0.25]
    t = Table(snap, colWidths=cws)
    t.setStyle(TableStyle([
        ("BACKGROUND",      (0,0),(-1,0), SAGE_DARK),
        ("ROWBACKGROUNDS",  (0,1),(-1,-1), [WHITE, CREAM_DARK]),
        ("LEFTPADDING",     (0,0),(-1,-1), 8),
        ("RIGHTPADDING",    (0,0),(-1,-1), 8),
        ("TOPPADDING",      (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",   (0,0),(-1,-1), 6),
        ("GRID",            (0,0),(-1,-1), 0.4, SAGE_PALE),
        ("VALIGN",          (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(PageBreak())
    return story


def build_kpi_dashboard(data, st):
    story = sec_header("02  |  KPI Dashboard", st)
    story.append(Paragraph(
        "All metrics below are sourced from the Instagram Graph API for the 28-day rolling period. "
        "Each KPI reflects organic performance. Derived metrics are calculated from the primary figures.",
        st["body"]))
    story.append(Spacer(1, 8))

    kpis = [
        ("reach",           "Reach",            "Unique accounts reached"),
        ("interactions",    "Interactions",      "All engagement actions"),
        ("accounts_engaged","Accounts Engaged",  "Unique engagers"),
        ("profile_views",   "Profile Views",     "Page visits"),
        ("website_clicks",  "Website Clicks",    "Bio & story link taps"),
        ("new_followers",   "New Followers",     "Net follower gain"),
        ("story_replies",   "Story Replies",     "Direct story responses"),
        ("eng_rate",        "Engagement Rate",   "Engaged ÷ Reach × 100"),
    ]

    def kpi_cell(key, label, desc):
        val = data.get(key,"—")
        if key == "eng_rate" and (not val or val=="—"):
            val = safe_pct(data.get("accounts_engaged","0"), data.get("reach","1"))
        display = str(val)
        if "%" not in display: display = fmt(val)
        return [
            Paragraph(display, st["kpi_big"]),
            Spacer(1,2),
            Paragraph(label.upper(), st["kpi_label"]),
            Paragraph(desc, ParagraphStyle("kd",fontSize=7.5,textColor=TEXT_LIGHT,
                                            fontName="Helvetica",leading=10)),
        ]

    cw = (COL_W - 9) / 4
    for chunk in [kpis[:4], kpis[4:]]:
        row = [kpi_cell(*k) for k in chunk]
        t = Table([row], colWidths=[cw]*4)
        t.setStyle(TableStyle([
            ("BACKGROUND",     (0,0),(-1,-1), WHITE),
            ("LEFTPADDING",    (0,0),(-1,-1), 12),
            ("TOPPADDING",     (0,0),(-1,-1), 12),
            ("BOTTOMPADDING",  (0,0),(-1,-1), 12),
            ("RIGHTPADDING",   (0,0),(-1,-1), 12),
            ("LINEBEFORE",     (0,0),(-1,-1), 4, SAGE_GREEN),
            ("BOX",            (0,0),(-1,-1), 0.5, SAGE_PALE),
            ("LINEAFTER",      (0,0),(2,-1),  0.5, SAGE_PALE),
            ("COLBACKGROUNDS", (0,0),(-1,-1), [WHITE, CREAM_DARK, WHITE, CREAM_DARK]),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 8))
    story.append(Paragraph("Derived & Calculated Metrics", st["h2"]))
    story.append(Spacer(1, 4))

    try:
        r  = float(str(data.get("reach","0")).replace(",",""))
        ae = float(str(data.get("accounts_engaged","0")).replace(",",""))
        i  = float(str(data.get("interactions","0")).replace(",",""))
        pv = float(str(data.get("profile_views","0")).replace(",",""))
        wc = float(str(data.get("website_clicks","0")).replace(",",""))
        derived = [
            ("Engagement Rate (ER)",       f"{ae/r*100:.2f}%" if r else "—", "Accounts Engaged / Reach × 100"),
            ("Interaction Rate",           f"{i/r*100:.2f}%"  if r else "—", "Total Interactions / Reach × 100"),
            ("Profile View Rate",          f"{pv/r*100:.2f}%" if r else "—", "Profile Views / Reach × 100"),
            ("Click-Through Rate (CTR)",   f"{wc/r*100:.3f}%" if r else "—", "Website Clicks / Reach × 100"),
            ("Click-to-Engage Ratio",      f"{wc/ae*100:.2f}%" if ae else "—", "Website Clicks / Accounts Engaged × 100"),
            ("Avg Daily Interactions",     f"{i/28:.0f}" if i else "—", "Total Interactions / 28 days"),
        ]
    except:
        derived = []

    if derived:
        dh = [[Paragraph("METRIC",st["th"]),Paragraph("VALUE",st["th"]),Paragraph("FORMULA",st["th"])]]
        for lbl, val, form in derived:
            dh.append([Paragraph(lbl,st["td_left"]),Paragraph(f"<b>{val}</b>",st["td"]),Paragraph(form,st["td_left"])])
        dt = Table(dh, colWidths=[COL_W*0.35,COL_W*0.18,COL_W*0.47])
        dt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,0), SAGE_GREEN),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE, CREAM_DARK]),
            ("LEFTPADDING",   (0,0),(-1,-1), 8),
            ("RIGHTPADDING",  (0,0),(-1,-1), 8),
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("GRID",          (0,0),(-1,-1), 0.4, SAGE_PALE),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ]))
        story.append(dt)
    story.append(PageBreak())
    return story


def build_content_performance(data, st):
    story = sec_header("03  |  Content Performance", st)
    posts = parse_posts_json(data.get("posts_data", "")) or parse_posts(data.get("top_posts", ""))

    story.append(Paragraph(
        "This section analyses post-level performance for the reporting period. "
        "Posts are ranked by engagement score (likes + comments). "
        "Content format distribution and individual post data are detailed below.",
        st["body"]))
    story.append(Spacer(1, 8))

    if not posts:
        story.append(Paragraph("Post-level data was not available for this reporting period.", st["body"]))
        story.append(PageBreak())
        return story

    # Content type summary
    type_counts = {}
    for p in posts:
        t = p.get("type","FEED").upper()
        type_counts[t] = type_counts.get(t,0) + 1

    story.append(Paragraph("Content Format Distribution", st["h2"]))
    story.append(Spacer(1, 4))
    type_h = [[Paragraph("FORMAT",st["th"]),Paragraph("POSTS",st["th"]),Paragraph("SHARE",st["th"]),
               Paragraph("AVG ENGAGEMENT",st["th"])]]
    for ptype, cnt in sorted(type_counts.items(), key=lambda x:-x[1]):
        type_posts = [p for p in posts if p.get("type","FEED").upper()==ptype]
        avg_eng = sum(p["eng_int"] for p in type_posts)/len(type_posts) if type_posts else 0
        type_h.append([
            Paragraph(ptype.replace("_"," "), st["td_left"]),
            Paragraph(str(cnt), st["td"]),
            Paragraph(f"{cnt/len(posts)*100:.0f}%", st["td"]),
            Paragraph(f"{avg_eng:.0f}", st["td"]),
        ])
    type_t = Table(type_h, colWidths=[COL_W*0.35,COL_W*0.18,COL_W*0.20,COL_W*0.27])
    type_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SAGE_MID),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,CREAM_DARK]),
        ("LEFTPADDING",   (0,0),(-1,-1),9),("RIGHTPADDING",(0,0),(-1,-1),9),
        ("TOPPADDING",    (0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("GRID",          (0,0),(-1,-1),0.4,SAGE_PALE),
    ]))
    story.append(type_t)
    story.append(Spacer(1, 10))

    # Post performance ranking
    story.append(Paragraph("Post Performance Ranking", st["h2"]))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Sorted by engagement score (likes + comments). Top post highlighted in green.", st["body_sm"]))
    story.append(Spacer(1, 4))

    ph = [[Paragraph("#",st["th"]),Paragraph("DATE",st["th"]),Paragraph("FORMAT",st["th"]),
           Paragraph("LIKES",st["th"]),Paragraph("COMMENTS",st["th"]),Paragraph("SCORE",st["th"]),Paragraph("LINK",st["th"])]]
    pr = []
    for i, p in enumerate(posts[:10]):
        url = p.get("url","")
        link_cell = Paragraph(f"<a href='{url}'><font color='#2E5D4B'>View →</font></a>", st["td"]) if url else Paragraph("—", st["td"])
        pr.append([
            Paragraph(f"<b>{i+1}</b>", st["td"]),
            Paragraph((p.get("date","—")[:10] if p.get("date") else "—"), st["td"]),
            Paragraph(p.get("type","—").replace("_"," "), st["td"]),
            Paragraph(str(p.get("likes","—")), st["td"]),
            Paragraph(str(p.get("comments","—")), st["td"]),
            Paragraph(f"<b>{p.get('eng_int','—')}</b>", st["td"]),
            link_cell,
        ])
    pcws = [COL_W*0.06,COL_W*0.14,COL_W*0.16,COL_W*0.14,COL_W*0.15,COL_W*0.14,COL_W*0.21]
    ts = [
        ("BACKGROUND",    (0,0),(-1,0), SAGE_DARK),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,CREAM_DARK]),
        ("LEFTPADDING",   (0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",    (0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),
        ("GRID",          (0,0),(-1,-1),0.4,SAGE_PALE),
        ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
    ]
    if pr:
        ts += [("BACKGROUND",(0,1),(-1,1),SAGE_LIGHT),("FONTNAME",(0,1),(-1,1),"Helvetica-Bold")]
    pt = Table(ph+pr, colWidths=pcws)
    pt.setStyle(TableStyle(ts))
    story.append(pt)
    story.append(Spacer(1,4))
    story.append(Paragraph("★ Highlighted row = top performing post of the period", st["caption"]))
    story.append(Spacer(1, 10))

    # Bar chart
    story.append(Paragraph("Engagement by Post — Visual Overview", st["h2"]))
    story.append(Spacer(1,4))
    chart_posts = [{"label": p.get("date","")[:10] if p.get("date") else f"Post {i+1}",
                    "value": p.get("eng_int",0), "type": p.get("type","FEED")}
                   for i, p in enumerate(posts[:8])]
    # Sort by date for chart
    chart_posts_dated = sorted(chart_posts, key=lambda x: x["label"])
    ch = max(90, len(chart_posts_dated)*22+20)
    story.append(BarChart(chart_posts_dated, COL_W, ch))
    story.append(Spacer(1,4))
    story.append(Paragraph("Bars show engagement score (likes + comments) per post, ordered by date.", st["caption"]))
    story.append(Spacer(1, 10))

    # Top post spotlight
    story.append(Paragraph("Top Performer Spotlight", st["h2"]))
    story.append(Spacer(1,4))
    top = posts[0]
    spot = [[
        Paragraph("<b>#1 Top Post</b>", ParagraphStyle("spt",fontSize=13,textColor=CREAM,
                                                        fontName="Helvetica-Bold",leading=17)),
        [Paragraph(f"Date: <b>{top.get('date','—')[:10]}</b>  |  Format: <b>{top.get('type','—').replace('_',' ')}</b>",
                   ParagraphStyle("sb",fontSize=9.5,textColor=CREAM,fontName="Helvetica",leading=14)),
         Spacer(1,4),
         Paragraph(f"👍 Likes: <b>{top.get('likes','—')}</b>  &nbsp;  💬 Comments: <b>{top.get('comments','—')}</b>  &nbsp;  ⚡ Score: <b>{top.get('eng_int','—')}</b>",
                   ParagraphStyle("sb2",fontSize=10,textColor=CREAM,fontName="Helvetica",leading=14)),
         Spacer(1,4),
         Paragraph(f"<a href='{top.get('url','#')}'><font color='#C8D9C7'>View Post →</font></a>",
                   ParagraphStyle("sl",fontSize=8.5,textColor=SAGE_PALE,fontName="Helvetica",leading=12))
         if top.get("url") else Spacer(1,1)],
    ]]
    st_t = Table(spot, colWidths=[COL_W*0.22, COL_W*0.78])
    st_t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), SAGE_DARK),
        ("LEFTPADDING",   (0,0),(-1,-1), 14),
        ("RIGHTPADDING",  (0,0),(-1,-1), 14),
        ("TOPPADDING",    (0,0),(-1,-1), 14),
        ("BOTTOMPADDING", (0,0),(-1,-1), 14),
        ("LINEBEFORE",    (0,0),(0,-1),  5, ACCENT_GOLD),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(st_t)
    story.append(PageBreak())
    return story


def build_ai_insights(data, st):
    story = sec_header("04  |  AI-Generated Insights", st)
    story.append(Spacer(1, 4))

    ai_text = data.get("ai_summary","No AI summary available.")
    sections_raw = re.split(r'\n(?=\d[\)\.]\s|\*\*[A-Z])', ai_text.strip())

    section_map = {
        "1": ("Performance Summary",      SAGE_GREEN),
        "2": ("Top Performing Post",      ACCENT_GOLD),
        "3": ("Strategic Recommendations",SAGE_DARK),
    }

    for sec in sections_raw:
        sec = sec.strip()
        if not sec: continue
        m = re.match(r'^(\d)[\)\.]\s*(.*)', sec, re.DOTALL)
        if m:
            num, content = m.group(1), m.group(2)
            label, accent = section_map.get(num, (f"Section {num}", SAGE_GREEN))
            # Label bar
            lb = Table([[Paragraph(f"<b>{num}. {label.upper()}</b>",
                                   ParagraphStyle("ail",fontSize=9,textColor=CREAM,
                                                   fontName="Helvetica-Bold",leading=12))]],
                       colWidths=[COL_W])
            lb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),accent),
                                     ("LEFTPADDING",(0,0),(-1,-1),12),
                                     ("TOPPADDING",(0,0),(-1,-1),7),
                                     ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
            story.append(lb)
            # Content
            clean = bold(content.replace('\n\n','<br/><br/>').replace('\n',' '))
            cb = Table([[Paragraph(clean, st["body"])]], colWidths=[COL_W])
            cb.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),WHITE),
                                     ("LEFTPADDING",(0,0),(-1,-1),14),
                                     ("RIGHTPADDING",(0,0),(-1,-1),14),
                                     ("TOPPADDING",(0,0),(-1,-1),10),
                                     ("BOTTOMPADDING",(0,0),(-1,-1),10),
                                     ("LINEBEFORE",(0,0),(-1,-1),4,accent),
                                     ("BOX",(0,0),(-1,-1),0.5,SAGE_PALE)]))
            story.append(cb)
            story.append(Spacer(1,6))
        else:
            clean = bold(sec.replace('\n\n','<br/><br/>').replace('\n',' '))
            story.append(Paragraph(clean, st["body"]))
            story.append(Spacer(1,4))

    story.append(PageBreak())
    return story


def build_recommendations(data, st):
    story = sec_header("05  |  Recommendations & Next Steps", st)
    story.append(Spacer(1, 10))

    # Extract recs from AI text or use defaults
    ai_text = data.get("ai_summary","")
    recs = []
    rec_m = re.search(r'[Rr]ecommendation[s]?[:\n]+(.*?)$', ai_text, re.DOTALL)
    if rec_m:
        raw = re.findall(r'[-•\d\.]\s*(.+?)(?=\n[-•\d\.]|\n\n|$)', rec_m.group(1), re.DOTALL)
        recs = [r.strip() for r in raw if r.strip()]

    if not recs:
        recs = [
            "Increase posting frequency to 4–5 times per week to sustain algorithmic reach and maintain audience engagement.",
            "Prioritise Reels and Carousel formats — these consistently outperform single-image posts for reach and saves.",
            "Add clear CTAs in every caption — direct followers to the bio link, encourage comments with a question, or prompt saves.",
            "Engage with comments within the first 60 minutes of posting to maximise early algorithmic distribution.",
            "Use Instagram Stories 3–5 times per week with interactive stickers (polls, questions, quizzes) to boost Story replies.",
        ]

    for i, rec in enumerate(recs[:5], 1):
        rec_row = [[
            Paragraph(f"<b>0{i}</b>", ParagraphStyle("rn",fontSize=18,textColor=SAGE_PALE,
                                                        fontName="Helvetica-Bold",leading=22,alignment=TA_CENTER)),
            Paragraph(bold(rec), st["body"]),
        ]]
        rt = Table(rec_row, colWidths=[COL_W*0.11, COL_W*0.89])
        rt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(0,-1), SAGE_DARK),
            ("BACKGROUND",    (1,0),(1,-1), WHITE),
            ("LEFTPADDING",   (0,0),(-1,-1),12),
            ("RIGHTPADDING",  (0,0),(-1,-1),12),
            ("TOPPADDING",    (0,0),(-1,-1),12),
            ("BOTTOMPADDING", (0,0),(-1,-1),12),
            ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
            ("BOX",           (0,0),(-1,-1),0.5,SAGE_PALE),
        ]))
        story.append(rt)
        story.append(Spacer(1,5))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Priority Focus Areas for Next Month", st["h2"]))
    story.append(Spacer(1,4))
    focus = [
        [Paragraph("AREA",st["th"]),Paragraph("CURRENT STATUS",st["th"]),Paragraph("TARGET ACTION",st["th"]),Paragraph("PRIORITY",st["th"])],
        [Paragraph("Content Frequency",st["td_left"]),Paragraph("Monitor cadence",st["td"]),Paragraph("Consistent schedule",st["td"]),Paragraph("🔴 High",st["td"])],
        [Paragraph("Format Mix",st["td_left"]),Paragraph("Review top formats",st["td"]),Paragraph("More Reels & Carousels",st["td"]),Paragraph("🔴 High",st["td"])],
        [Paragraph("Follower Growth",st["td_left"]),Paragraph(fmt(data.get("new_followers","0")),st["td"]),Paragraph("Collabs & CTAs",st["td"]),Paragraph("🟡 Medium",st["td"])],
        [Paragraph("Story Engagement",st["td_left"]),Paragraph(fmt(data.get("story_replies","0")),st["td"]),Paragraph("Interactive stickers",st["td"]),Paragraph("🟡 Medium",st["td"])],
        [Paragraph("Website Traffic",st["td_left"]),Paragraph(fmt(data.get("website_clicks","0")),st["td"]),Paragraph("Strengthen CTAs",st["td"]),Paragraph("🔴 High",st["td"])],
    ]
    ft = Table(focus, colWidths=[COL_W*0.27,COL_W*0.22,COL_W*0.32,COL_W*0.19])
    ft.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0), SAGE_GREEN),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE,CREAM_DARK]),
        ("LEFTPADDING",   (0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",    (0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("GRID",          (0,0),(-1,-1),0.4,SAGE_PALE),
        ("VALIGN",        (0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(ft)
    story.append(Spacer(1,14))

    # Disclaimer
    story.append(HRFlowable(width=COL_W,thickness=0.5,color=SAGE_PALE,spaceAfter=8))
    story.append(Paragraph("Data Notes & Disclaimer", st["h3"]))
    for d in [
        "All metrics are sourced from the Instagram Graph API via Meta Business Suite, reflecting the 28-day rolling period ending on the report date.",
        "Reach represents unique accounts — the same user is counted once regardless of impression frequency.",
        "Engagement Rate = Accounts Engaged ÷ Reach × 100. Industry benchmarks vary by account size and vertical.",
        "Post data shows recent posts sorted by engagement; figures include likes and comments only (saves not included in Graph API v18+).",
        "New Followers reflects net growth (follows minus unfollows) and may differ from gross follower additions.",
        "Data accuracy is subject to Meta API reporting delays, typically 24–48 hours after the period end.",
    ]:
        story.append(Paragraph(f"•  {d}", st["disclaimer"]))
    story.append(Spacer(1,8))
    story.append(Paragraph(
        "This report was prepared by Sage Media exclusively for the named client. "
        "Unauthorised reproduction or distribution is strictly prohibited.",
        st["footer_sm"]))
    return story


# ── Main PDF builder ─────────────────────────────────────────────────
def generate_pdf(data):
    buf = io.BytesIO()
    st = make_styles()
    page_num[0] = 0

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=20*mm,
        title=f"{data.get('brand_name','Report')} — Instagram Report — {data.get('month','')}",
    )

    story = []
    story += build_cover(data, st)
    story += build_executive_summary(data, st)
    story += build_kpi_dashboard(data, st)
    story += build_content_performance(data, st)
    story += build_ai_insights(data, st)
    story += build_recommendations(data, st)

    doc.build(story, onFirstPage=cover_bg, onLaterPages=page_bg)
    buf.seek(0)
    return buf


# ── Routes ────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/generate", methods=["POST"])
def generate():
    try:
        # Accept both form-encoded (from Make) and JSON
        content_type = request.content_type or ""
        if "application/json" in content_type:
            data = request.get_json(force=True) or {}
        else:
            # form-urlencoded or multipart
            data = request.form.to_dict()
            if not data:
                data = request.get_json(force=True) or {}

        if not data:
            return jsonify({"error": "No data received"}), 400

        pdf_buf = generate_pdf(data)
        fname = (f"{data.get('brand_name','report').replace(' ','_')}_"
                 f"{data.get('month','').replace(' ','_')}_Report.pdf")
        return send_file(pdf_buf, mimetype="application/pdf",
                         as_attachment=True, download_name=fname)
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
