"""
AI 뉴스 수집 및 요약 스크립트
- Google News RSS + 주요 기술 매체 RSS에서 AI 뉴스 수집
- LM Studio (localhost:1234) 로컬 AI로 요약
- 결과를 news_data.json으로 저장 → dashboard.html에서 표시
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

LMSTUDIO_URL = "http://localhost:1234/v1/chat/completions"
OUTPUT_FILE = Path(__file__).parent / "news_data.json"

# Google News RSS 피드
GOOGLE_FEEDS = {
    # 한국어 뉴스
    "최신 AI 뉴스": {"query": "AI+인공지능", "lang": "ko"},
    "ChatGPT/GPT": {"query": "ChatGPT+GPT", "lang": "ko"},
    "LLM": {"query": "LLM+Claude+Gemini+대규모언어모델", "lang": "ko"},
    "AI 연구": {"query": "AI연구+딥러닝+머신러닝", "lang": "ko"},
    "AI 산업": {"query": "AI기업+AI투자+AI스타트업", "lang": "ko"},
    # 영어 뉴스
    "AI Global": {"query": "artificial+intelligence+AI", "lang": "en"},
    "OpenAI & GPT": {"query": "OpenAI+GPT+ChatGPT", "lang": "en"},
    "AI Research": {"query": "AI+research+deep+learning+LLM", "lang": "en"},
}

# 주요 기술 매체 직접 RSS 피드
DIRECT_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "Wired AI": "https://www.wired.com/feed/tag/ai/latest/rss",
}


def fetch_google_news(query, lang="ko", count=5):
    """Google News RSS에서 뉴스 가져오기"""
    if lang == "en":
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en&gl=US&ceid=US:en"
    else:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, timeout=10)
        root = ET.fromstring(res.content)
        items = root.findall(".//item")[:count]

        articles = []
        for item in items:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            source = item.find("source")
            source_name = source.text if source is not None else ""
            pub_date = item.findtext("pubDate", "")

            articles.append({
                "title": title,
                "link": link,
                "source": source_name,
                "date": pub_date,
            })
        return articles
    except Exception as e:
        print(f"  뉴스 수집 실패 ({query}): {e}")
        return []


def fetch_direct_rss(feed_url, source_name, count=5):
    """일반 RSS 피드에서 뉴스 가져오기"""
    try:
        res = requests.get(feed_url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        root = ET.fromstring(res.content)

        # RSS 2.0 형식
        items = root.findall(".//item")[:count]
        # Atom 형식 fallback
        if not items:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            items = root.findall(".//atom:entry", ns)[:count]

        articles = []
        for item in items:
            # RSS 2.0
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "") or item.findtext("dc:date", "") or ""

            # Atom fallback
            if not link:
                link_el = item.find("{http://www.w3.org/2005/Atom}link")
                if link_el is not None:
                    link = link_el.get("href", "")
            if not title:
                title = item.findtext("{http://www.w3.org/2005/Atom}title", "")
            if not pub_date:
                pub_date = item.findtext("{http://www.w3.org/2005/Atom}updated", "")

            if title:
                articles.append({
                    "title": title.strip(),
                    "link": link,
                    "source": source_name,
                    "date": pub_date,
                })
        return articles
    except Exception as e:
        print(f"  RSS 수집 실패 ({source_name}): {e}")
        return []


def translate_titles(articles):
    """영어 뉴스 제목을 한글로 번역 (LM Studio, 10개씩 나누어 처리)"""
    en_articles = [a for a in articles if not any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in a["title"])]
    if not en_articles:
        return

    translated_count = 0
    # 10개씩 배치로 나누어 번역
    batch_size = 10
    for batch_start in range(0, len(en_articles), batch_size):
        batch = en_articles[batch_start:batch_start + batch_size]
        titles = "\n".join(f"{i+1}. {a['title']}" for i, a in enumerate(batch))
        prompt = f"""다음 영어 뉴스 제목들을 자연스러운 한국어로 번역해주세요.
번호와 번역만 출력하세요. 다른 설명은 하지 마세요.

{titles}"""

        try:
            res = requests.post(
                LMSTUDIO_URL,
                json={
                    "model": "local-model",
                    "messages": [
                        {"role": "system", "content": "영어를 한국어로 번역합니다. 번호와 번역만 출력합니다."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 500,
                },
                timeout=120,
            )
            result = res.json()["choices"][0]["message"]["content"].strip()
            lines = [l.strip() for l in result.split("\n") if l.strip()]

            for line in lines:
                for i, a in enumerate(batch):
                    prefix = f"{i+1}."
                    if line.startswith(prefix):
                        translated = line[len(prefix):].strip()
                        if translated:
                            a["title"] = translated
                            translated_count += 1
                        break
        except Exception as e:
            print(f"  배치 번역 실패 (원본 유지): {e}")

    print(f"  {translated_count}/{len(en_articles)}개 영어 제목 번역 완료")


def summarize_with_lmstudio(articles):
    """LM Studio 로컬 AI로 뉴스 요약"""
    if not articles:
        return "수집된 뉴스가 없습니다."

    news_text = "\n".join(
        f"{i+1}. {a['title']} ({a['source']})" for i, a in enumerate(articles)
    )

    prompt = f"""다음은 한국/해외 다양한 매체에서 수집한 AI 뉴스 헤드라인입니다.
모두 한국어로 분석하고 상세하게 요약해주세요.

뉴스 목록:
{news_text}

요구사항:
- 10~15줄로 국내외 핵심 트렌드를 상세히 요약
- 주요 뉴스별로 구체적인 내용과 의미를 설명
- 카테고리별(국내 동향, 해외 동향, 기술 트렌드, 산업 전망)로 나누어 정리
- 중요한 키워드(회사명, 기술명, 서비스명 등)는 그대로 유지
- 읽기 쉽게 문단을 나누어 작성"""

    try:
        res = requests.post(
            LMSTUDIO_URL,
            json={
                "model": "local-model",
                "messages": [
                    {"role": "system", "content": "당신은 AI 뉴스 전문 분석가입니다. 핵심만 간결하게 요약합니다."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 1500,
            },
            timeout=120,
        )
        return res.json()["choices"][0]["message"]["content"].strip()
    except requests.ConnectionError:
        return "LM Studio가 실행되지 않았습니다. LM Studio를 실행하고 Start Server를 눌러주세요."
    except Exception as e:
        return f"요약 실패: {e}"


def main():
    print("=" * 50)
    print(f"AI 뉴스 수집 및 요약 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    result = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "categories": [],
    }

    all_articles = []

    # 1) Google News RSS 수집
    for category, feed_info in GOOGLE_FEEDS.items():
        print(f"\n[{category}] 뉴스 수집 중...")
        articles = fetch_google_news(feed_info["query"], lang=feed_info["lang"], count=5)
        all_articles.extend(articles)
        print(f"  {len(articles)}개 수집 완료")

        result["categories"].append({
            "name": category,
            "articles": articles,
        })

    # 2) 주요 기술 매체 직접 RSS 수집
    for source_name, feed_url in DIRECT_FEEDS.items():
        print(f"\n[{source_name}] RSS 수집 중...")
        articles = fetch_direct_rss(feed_url, source_name, count=5)
        all_articles.extend(articles)
        print(f"  {len(articles)}개 수집 완료")

        result["categories"].append({
            "name": source_name,
            "articles": articles,
        })

    print(f"\n총 {len(all_articles)}개 기사 수집 완료")

    print("\n영어 뉴스 제목 번역 중 (LM Studio)...")
    translate_titles(all_articles)

    print("\n전체 뉴스 요약 중 (LM Studio)...")
    summary = summarize_with_lmstudio(all_articles)
    result["summary"] = summary
    print(f"  요약 완료!")

    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {OUTPUT_FILE}")
    print(f"\n--- 요약 ---\n{summary}")


if __name__ == "__main__":
    main()
