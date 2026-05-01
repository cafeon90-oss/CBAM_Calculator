# 🌍 EU CBAM 영향 계산기 / EU CBAM Impact Calculator

**한국 기업의 EU 탄소국경조정제도(CBAM) 부담을 시뮬레이션하는 Streamlit 도구**
*A Streamlit tool to simulate EU CBAM cost exposure for Korean exporters.*

[![Built by](https://img.shields.io/badge/Built%20by-Song%20BK-4FC3F7)](https://github.com/cafeon90-oss)
[![License: MIT](https://img.shields.io/badge/License-MIT-81C784.svg)](LICENSE)
[![Sister Tool](https://img.shields.io/badge/Sister-CCUS%20Benchmark-B388FF)](https://github.com/cafeon90-oss/CCUS_benchmark)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B)](https://streamlit.io/)

---

## 🇰🇷 한국어

### 목적

EU CBAM (Carbon Border Adjustment Mechanism, 탄소국경조정제도)이 **2026년 1월 1일 본격 시행**됨에 따라, 한국 주요 수출기업(POSCO, 현대제철, 시멘트, 알루미늄, 비료, 수소)이 부담할 CBAM 비용을 시뮬레이션하고, **탄소감축 수단(CCS, DRI-H₂, EAF, RE100, Bio-CCS)** 적용 시 회피 가능액을 계산합니다.

### 핵심 수식

```
CBAM cost = (SEE − Free EU benchmark) × Phase-in factor × EUA × import volume
```

- **SEE** (Specific Embedded Emissions): 단위 제품당 내재 탄소배출량 [tCO₂/t]
- **Phase-in factor**: 2026 2.5% → 2034 100% (선형 ramp)
- **EUA**: EU ETS 탄소배출권 가격 (€/tCO₂)
- **Free benchmark**: EU 무상할당 벤치마크 (sector·공정별)

### 9개 탭 구성

| # | 탭 | 내용 |
|---|---|---|
| ① | 종합 영향 | 6개 sector × 한국 평균 SEE × EU benchmark 비교 |
| ② | Sector별 분석 | 선택 sector deep-dive (default vs 한국 vs benchmark) |
| ③ | 한국 기업 영향 | 9개 프리셋 기업 비교 (POSCO, 현대제철 BF/EAF, 시멘트 등) |
| ④ | 감축 시뮬레이터 | "CBAM=0 만들려면 얼마 감축?" 역산 + BEP 분석 |
| ⑤ | CCUS 연계 | 자매 도구(CCUS Benchmark) 연결 — Phase 2 |
| ⑥ | 시간 흐름 | 2023~2034 phase-in 시각화 + 회사별 trajectory |
| ⑦ | Custom 입력 | Multi-year 비교 + EUA 가격 민감도 |
| ⑧ | 방법론 | 계산식, 가정, 한계 |
| ⑨ | 참고문헌 | 30+ 출처 카탈로그 (regulation, report, paper, market) |

### 시나리오 프리셋 (9개 + Custom)

1. 🇰🇷 POSCO (BF-BOF, ~75 Mt/yr)
2. 🇰🇷 현대제철 (BF + EAF mix)
3. 🇰🇷 현대제철 (Pure Scrap-EAF)
4. 🇰🇷 쌍용·한일시멘트
5. 🇰🇷 노벨리스 코리아 (Aluminum)
6. 🇰🇷 한화솔루션 (NH₃·비료)
7. 🇰🇷 SK E&S (Gray H₂)
8. 🇰🇷 SK E&S + CCS (Blue H₂) — *CCS 효과 데모*
9. 🌍 EU 베스트 (DRI-H₂ 철강) — 참조용
10. ✏️ Custom (사용자 직접 입력)

### 자동 데이터 갱신

- **EUA 가격**: GitHub Actions가 매주 월요일 09:00 KST에 Sandbag/TradingEconomics에서 fetch → `data/eua_price.json` commit. Streamlit `@st.cache_data(ttl=86400)`.
- **POSCO SEE**: 정적값 + 출처 link + 사용자 슬라이더 override (POSCO ESG 보고서는 연 1회 갱신).
- **CCUS COCA**: Phase 2에서 자매 도구 `data/ccus_metrics.json` 연결 예정 (현재는 stub mirror).

### 설치 및 실행

```bash
# 1. clone
git clone https://github.com/cafeon90-oss/CBAM_calculator.git
cd CBAM_calculator

# 2. (권장) 가상환경
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate          # Windows

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 실행
streamlit run app.py
```

### 디렉토리 구조

```
CBAM_calculator/
├── app.py                          # 메인 Streamlit 앱
├── requirements.txt
├── README.md                       # 이 파일
├── LICENSE                         # MIT
├── .streamlit/
│   └── config.toml                 # 다크모드 + 서버 설정
├── data/
│   └── eua_price.json              # EUA 가격 (GitHub Actions 자동 갱신)
└── .github/
    └── workflows/
        └── eua_fetch.yml           # 주 1회 EUA 가격 fetch cron
```

### 자매 도구

🌫️ **[CCUS 기술 벤치마크](https://github.com/cafeon90-oss/CCUS_benchmark)** — 한국·미국·EU의 5+1개 CCUS 흡수제 기술의 COCA·SPECCA·CAPEX 비교. CBAM 회피를 위한 CCS 도입 시 BEP 분석 시 본 도구와 데이터 연계.

### 핵심 출처

- **Regulation**: EU Regulation 2023/956, EU IR 2025/2621
- **Korea Reports**: 대한상의 SGI Brief 22 (2024), KOTRA 공급망 인사이트, 한국무역협회
- **Industry**: POSCO Climate Risk 2025, InfluenceMap 2024
- **Market**: EEX, Sandbag, ICE EUA Futures
- **Standards**: IEA, IEAGHG, NETL, World Steel Association

전체 30+ 출처는 앱 내 탭 ⑨ 참고문헌 또는 [REFS 섹션](app.py#L600) 참조.

### 기여·문의

- 🐙 GitHub: [cafeon90-oss](https://github.com/cafeon90-oss)
- 💼 LinkedIn: [Bongkwan Song](https://www.linkedin.com/in/bongkwan-song-95a0213ba/)
- 📝 Blog: [CDR Master](https://cdrmaster.tistory.com/)
- 📧 Email: cafeon90@gmail.com

### License

MIT License © 2026 송봉관 / Song BK. 자세한 내용은 [LICENSE](LICENSE) 참조.

---

## 🇬🇧 English

### Purpose

The **EU CBAM (Carbon Border Adjustment Mechanism)** entered its definitive phase on **1 January 2026**. This Streamlit tool helps Korean exporters in the six covered sectors (steel, cement, aluminum, fertilizer, hydrogen, electricity) **simulate annual CBAM exposure** and **evaluate avoidance scenarios** through carbon abatement options including CCS, DRI-H₂, EAF conversion, RE100, and Bio-CCS.

### Core Formula

```
CBAM cost = (SEE − Free EU benchmark) × Phase-in factor × EUA × import volume
```

- **SEE** (Specific Embedded Emissions) — tCO₂ per ton of product
- **Phase-in factor** — ramps from 2.5% in 2026 to 100% in 2034
- **EUA** — EU ETS allowance price (€/tCO₂)
- **Free benchmark** — EU free allocation benchmark per sector/process

### 9 Tabs

| # | Tab | Description |
|---|---|---|
| ① | Overview | 6-sector comparison (Korea avg vs EU benchmark) |
| ② | Sector Deep-dive | Selected sector: default vs Korea vs benchmark |
| ③ | Korean Companies | 9 preset comparison (POSCO, Hyundai Steel, etc.) |
| ④ | Abatement Sim | "How much reduction needed for CBAM=0?" + BEP |
| ⑤ | CCUS Linkage | Sister tool integration — Phase 2 |
| ⑥ | Timeline | 2023~2034 phase-in viz + per-company trajectory |
| ⑦ | Custom Input | Multi-year compare + EUA sensitivity |
| ⑧ | Methodology | Formulas, assumptions, limitations |
| ⑨ | References | 30+ source catalog (regulation/report/paper/market) |

### Auto Data Refresh

- **EUA price**: GitHub Actions cron weekly (Mon 09:00 KST) → fetches from Sandbag/TradingEconomics → commits to `data/eua_price.json`. Streamlit caches via `@st.cache_data(ttl=86400)`.
- **POSCO SEE**: Static value + source link + user slider override (POSCO ESG report annual).
- **CCUS COCA**: Phase 2 will fetch live from sister tool's `data/ccus_metrics.json`. Currently uses stub mirror.

### Quick Start

```bash
git clone https://github.com/cafeon90-oss/CBAM_calculator.git
cd CBAM_calculator
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### Sister Tool

🌫️ **[CCUS Technology Benchmark](https://github.com/cafeon90-oss/CCUS_benchmark)** — Compares 5+1 CCUS solvent/process technologies (COCA, SPECCA, CAPEX) for Korea/US/EU contexts. The CBAM calculator integrates this data for CCS-based abatement BEP analysis.

### Key Data Sources

- **Regulation**: EU Regulation 2023/956, EU IR 2025/2621
- **Korea**: KCCI SGI Brief 22 (2024), KOTRA Supply Chain Insight, KITA
- **Industry**: POSCO Climate Risk 2025, InfluenceMap 2024
- **Market**: EEX, Sandbag, ICE EUA Futures
- **Standards**: IEA, IEAGHG, NETL, World Steel Association

Full reference catalog (30+ entries) inside the app at Tab ⑨ References.

### License

MIT © 2026 Song BK (송봉관). See [LICENSE](LICENSE).

### Author

| | |
|---|---|
| 👤 Name | 송봉관 / Song BK (Bongkwan Song) |
| 🎯 Specialty | DAC & CCUS Technology Commercialization |
| 🐙 GitHub | [cafeon90-oss](https://github.com/cafeon90-oss) |
| 💼 LinkedIn | [Bongkwan Song](https://www.linkedin.com/in/bongkwan-song-95a0213ba/) |
| 📝 Blog | [CDR Master](https://cdrmaster.tistory.com/) |
| 📧 Email | cafeon90@gmail.com |

---

## 📋 Limitations & Disclaimer

This tool is for **educational and analytical purposes only**. All numbers are estimates based on publicly available information. Users should validate with their own verified data before making business decisions. This is not financial, legal, or regulatory advice.

본 도구는 **교육·분석 목적**입니다. 모든 수치는 공개된 정보 기반의 추정값이며, 비즈니스 의사결정 전 자체 검증된 데이터로 확인이 필요합니다. 재무·법률·규제 자문이 아닙니다.
