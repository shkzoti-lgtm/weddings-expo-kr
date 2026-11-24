# -*- coding: utf-8 -*-
"""cpaad 웨딩박람회 목록 파서 — weddings-expo.kr 용
   입력: ad.cpaad.co.kr/wedunited01drc/{ID} 페이지 HTML
   출력: [지역, 행사명, 시작일, 종료일, 장소, 상태, 이미지, 신청링크, 혜택]"""
import re, datetime, unicodedata

REGION_MAP = {
    "서울": "서울", "경기도": "경기", "인천": "인천", "부산": "부산",
    "충청도": "충청", "전라도": "전라", "강원도": "강원",
    "경상도": "경상", "제주도": "제주",
}

def _txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""

def _abs(u):
    if not u: return ""
    if u.startswith("//"): return "https:" + u
    if u.startswith("http"): return u
    return "https://ad.cpaad.co.kr" + ("" if u.startswith("/") else "/") + u

def parse_dates(s, today=None):
    """'11월 28일(토) ~ 11월 29일(일)' → (시작, 종료, 상시여부)
       '매주 주말', '상시' 등 날짜가 없으면 상시로 본다."""
    today = today or datetime.date.today()
    nums = re.findall(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", s)
    if not nums:
        return None, None, True

    def mk(mm, dd):
        y = today.year
        try: d = datetime.date(y, int(mm), int(dd))
        except ValueError: return None
        # 연말·연초 경계: 지난 날짜로 6개월 이상 벌어지면 내년으로 본다
        if (today - d).days > 180: d = d.replace(year=y + 1)
        return d

    s1 = mk(*nums[0])
    e1 = mk(*nums[1]) if len(nums) > 1 else s1
    if s1 and e1 and e1 < s1:
        e1 = e1.replace(year=e1.year + 1)
    return s1, e1, False


METRO = ("대전", "대구", "울산", "광주", "세종")
SINGLE_REGION = ("서울", "인천", "부산", "제주")

def city_of(region, place):
    """권역 + 주소에서 도시명을 뽑는다.
       서울·인천·부산·제주 → 권역명 그대로
       광역시(대전·대구·울산·광주·세종) → 주소 첫 단어
       그 외 → 주소의 ○○시 / ○○군"""
    if region in SINGLE_REGION:
        return region
    head = re.sub(r"\s+", " ", str(place or "")).strip()
    for m in METRO:
        if head.startswith(m):
            return m
    mt = re.search(r"([가-힣]{2,4})(시|군)(?![가-힣])", head)
    if mt and mt.group(1) not in ("특별", "광역", "통합특별"):
        return mt.group(1)
    return None

def parse(html_text, today=None):
    from bs4 import BeautifulSoup
    today = today or datetime.date.today()
    soup = BeautifulSoup(html_text, "html.parser")

    rows, skipped = [], []
    for wrap in soup.select(".goods_wrap01"):
        # 블록 바로 앞의 제목에서 권역을 읽는다
        label = ""
        node = wrap.find_previous(string=re.compile(r"(웨딩박람회 일정|웨딩홀/스드메/예물)"))
        if node: label = re.sub(r"\s+", " ", str(node)).strip()
        region = None
        for k, v in REGION_MAP.items():
            if label.startswith(k): region = v; break
        if region is None:
            continue   # '웨딩홀/스드메/예물' 묶음은 지역 일정이 아니라 제외

        for c in wrap.select(".goods01"):
            name = _txt(c.select_one(".ad_title"))
            date_s = _txt(c.select_one(".ad_date"))
            place = _txt(c.select_one(".ad_location"))
            info = _txt(c.select_one(".ad_info"))
            a = c.find("a"); img = c.find("img")
            link = _abs(a.get("href") if a else "")
            image = _abs(img.get("src") if img else "")
            if not name or not link:
                skipped.append(name or "(제목없음)"); continue

            s1, e1, always = parse_dates(date_s, today)
            if always:
                start = end = ""
            else:
                if not s1: skipped.append(name); continue
                if e1 < today: continue          # 이미 끝난 행사 제외
                start, end = s1.isoformat(), e1.isoformat()

            city = city_of(region, place)
            if not city:
                skipped.append(name); continue
            rows.append([city, name, start, end, place, "모집중", image, link, info])

    # 중복 제거 (같은 이름+시작일)
    seen, uniq = set(), []
    for r in rows:
        k = (r[1], r[2])
        if k in seen: continue
        seen.add(k); uniq.append(r)
    return uniq, skipped
