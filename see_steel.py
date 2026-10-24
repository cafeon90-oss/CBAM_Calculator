"""철강 SEE(내재배출량)·SEFA(무상할당 공제) 산정 — 화면 코드 없는 순수 계산 모듈.

근거 (확정기간 2026~):
- 이행규정 (EU) 2025/2547 (산정방법) — 물질수지 Annex II B.3.2, 귀속배출 Annex III A.3 식 55,
  폐가스 보정 식 53·54, SEE 식 59–63. 철강은 직접배출만 (소결광 2601 12 00만 간접배출 포함).
- 이행규정 (EU) 2025/2620 Annex (무상할당 공제) — 실측: Column A + 전구체 SEFA, 기본값: Column B.
- 이행규정 (EU) 2025/2621 (+ 2026/1740 정정) — 국가별 기본값. '-'·미등재 → 기타국가, 원산지 불명 → Annex IV.
- 집행위 가이던스 No.3·No.4·No.5d (2026-08-14) — 표준계수 표 4-7·4-9·4-11, 철강 계산 예시.

1단계 범위: 설치 통합(bubble) 방식, 탄소강 열연(7208)·슬래브(7207 12 10), 경로 C/D/E.
"""
from __future__ import annotations

import math

C_TO_CO2 = 3.664          # t CO₂ / t C
EF_NG = 56.1              # t CO₂ / TJ — 폐가스 보정의 천연가스 기준 (Annex II G)
WG_EXPORT_CORR = 0.667    # 수출 폐가스 보정 효율 계수 (식 54)
EF_HEAT_DEFAULT = round(EF_NG / 0.9, 1)   # 62.3 t CO₂/TJ — 천연가스 보일러 효율 90% 가정
KR_GRID_EF = 0.475        # t CO₂/MWh — 가이던스 5d 예시가 인용한 기본값법 Annex II 한국 값

ROUTES = {
    "C": "C 고로-전로 (BF-BOF)",
    "D": "D DRI-전기로 (DRI-EAF)",
    "E": "E 고철 전기로 (Scrap-EAF)",
}
PRODUCTS = {
    "7208": "열연강판 (CN 7208)",
    "7207": "슬래브 (CN 7207 12 10)",
}
ROUTE_SECTOR = {"C": "steel_BF_BOF", "D": "steel_DRI_EAF", "E": "steel_scrap_EAF"}

# ── 물질수지 물질 목록: (표시 이름, 단위, 기본 계수 t CO₂/단위, 출처) ─────────────
# 계수 = 탄소함량 × 3.664 (또는 배출계수 × 순발열량). 실측 탄소함량이 있으면 그 값으로 덮어쓴다.
MATERIALS = {
    # 투입
    # 연료는 배출계수(tCO₂/TJ) × 순발열량(GJ/t) / 1000 — 반올림하지 않고 그대로 곱한다
    "coke":          ("코크스", "t", 107.0 * 28.2 / 1000, "107 tCO₂/TJ × 28.2 GJ/t (표 4-7)"),
    "coke_breeze":   ("분코크스", "t", 107.0 * 28.2 / 1000, "코크스와 동일"),
    "pci_coal":      ("미분탄 (기타 역청탄)", "t", 94.6 * 25.8 / 1000, "94.6 tCO₂/TJ × 25.8 GJ/t"),
    "anthracite":    ("무연탄", "t", 98.3 * 26.7 / 1000, "98.3 tCO₂/TJ × 26.7 GJ/t"),
    "natural_gas":   ("천연가스", "GJ", 56.1 / 1000, "56.1 tCO₂/TJ"),
    "natural_gas_t": ("천연가스", "t", 56.1 * 48.0 / 1000, "56.1 tCO₂/TJ × 48.0 GJ/t"),
    "fuel_oil":      ("중유", "GJ", 77.4 / 1000, "77.4 tCO₂/TJ (표 4-7)"),
    "electrode":     ("전기로 전극", "t", 3.00, "표 4-11"),
    "charge_carbon": ("가탄제 (charge carbon)", "t", 3.04, "표 4-11"),
    "petcoke":       ("석유 코크스", "t", 3.19, "표 4-11"),
    "limestone":     ("석회석 CaCO₃", "t", 0.440, "표 4-9"),
    "dolomite":      ("백운석 CaMg(CO₃)₂", "t", 88.02 / 184.40, "화학양론 2CO₂ / CaMg(CO₃)₂ = 0.477"),
    "lime":          ("생석회 CaO", "t", 0.0, "탄산염 아님 — 잔류 탄소만 (실측 입력)"),
    "iron_ore":      ("철광석", "t", 0.00084, "탄소 0.023% (가이던스 5d 예시)"),
    "plastic_waste": ("폐플라스틱", "t", 2.506, "탄소 68.4% (가이던스 5d 예시)"),
    "steel_scrap":   ("강 스크랩", "t", 0.04, "표 4-11"),
    "iron_scrap":    ("철 스크랩", "t", 0.15, "표 4-11"),
    "other_in":      ("기타 투입 (계수 직접 입력)", "t", 0.0, "직접 입력"),
    # 산출 (탄소가 배출되지 않고 나가는 것 — 계산 시 차감)
    "steel_out":     ("산출: 강 제품", "t", 0.04, "표 4-11 (실측 탄소함량 권장)"),
    "pig_iron_out":  ("산출: 판매 선철", "t", 0.15, "표 4-11"),
    "scrap_out":     ("산출: 공정 스크랩 (외부로 나가는 것)", "t", 0.04, "표 4-11 — 공정에 되돌리는 스크랩은 넣지 않음"),
    "slag_out":      ("산출: 슬래그", "t", 0.0011, "탄소 0.03% (가이던스 5d 예시)"),
    "dust_out":      ("산출: 분진·슬러지", "t", 0.0, "직접 입력"),
    "other_out":     ("산출: 기타 (계수 직접 입력)", "t", 0.0, "직접 입력"),
}
OUTPUT_KEYS = {k for k in MATERIALS if k.endswith("_out")}


def material_label(key: str) -> str:
    name, unit, _, _ = MATERIALS[key]
    return f"{name} ({unit})"


LABEL_TO_KEY = {material_label(k): k for k in MATERIALS}

# ── 전구체: (이름, DV 엑셀 CN, 탄소 tCO₂/t 기본, Column B {연도구분: 값}) ───────────
# Column B: 이행규정 2025/2620 Annex 5절 (집행위 Excel 'CBAM Benchmarks_20260206').
# 연도구분 None = 연도 무관, "1" = 2026~27, "2" = 2028~30.
PRECURSORS = {
    "sinter":   ("소결광·펠릿 (2601 12 00)", 0.0,   {None: 0.086}),
    "pig_iron": ("선철 (7201)",              0.15,  {None: 1.210}),
    "dri":      ("DRI·HBI (7203)",          0.07,  {None: 0.397}),
    "slab":     ("슬래브 (7207 12 10)",      0.04,  {None: 1.364}),
    "hrc":      ("열연강판 (7208)",          0.04,  {None: 1.370}),
    "femn":     ("페로망간 고탄소 (7202 11)", 0.103, {"1": 1.361, "2": 1.277}),
    "fecr":     ("페로크롬 고탄소 (7202 41)", 0.191, {"1": 1.142, "2": 1.106}),
    "feni":     ("페로니켈 (7202 60 00)",     0.055, {"1": 2.390, "2": 2.295}),
}
PRECURSOR_LABEL_TO_KEY = {v[0]: k for k, v in PRECURSORS.items()}

# 국가별 기본값 (총배출, t CO₂/t) — 집행위 Excel 'DV correcting act_final update_06.08'
# (IR 2025/2621, IR 2026/1740 정정). None = 엑셀에 '-' → 기타국가 값 사용.
_DV_KEYS = ("sinter", "pig_iron", "femn", "fecr", "feni", "dri", "slab", "hrc")
_DV_ROWS = {
    "한국":      (0.130, 1.540, 1.690, 2.350, 3.480, None,  2.118, 2.118),
    "중국":      (0.260, 1.660, 1.690, 2.350, 6.150, None,  3.169, 3.187),
    "일본":      (0.200, 1.960, 1.690, 2.350, 3.480, None,  2.100, 2.100),
    "인도":      (0.340, 2.530, 1.690, 2.350, 3.480, 4.200, 4.270, 4.280),
    "베트남":    (1.110, 2.190, 1.690, None,  3.480, None,  2.350, 2.350),
    "인도네시아": (None,  7.920, 1.690, None,  6.150, None,  8.230, 8.230),
    "대만":      (0.220, 1.860, None,  None,  None,  None,  2.298, 2.310),
    "말레이시아": (None,  None,  1.690, 2.350, 3.480, None,  None,  None),
    "브라질":    (0.200, 1.478, 1.690, 2.350, 3.480, None,  1.610, 1.620),
    "러시아":    (1.610, 3.040, 1.690, None,  3.480, 2.010, 3.210, 3.430),
    "남아공":    (None,  3.470, 1.690, 2.350, 3.480, 0.760, 4.030, 4.140),
    "호주":      (0.090, 2.790, 1.690, 2.350, 3.480, None,  2.920, 2.970),
    "미국":      (0.680, 1.210, 1.690, 2.350, 3.480, 0.450, 1.390, 1.400),
    "기타국가":  (0.686, 3.480, 1.690, 2.350, 4.014, 1.325, 3.996, 4.049),
    "원산지 불명": (1.610, 7.920, 1.690, 2.350, 6.150, 4.200, 8.230, 8.230),   # Annex IV (최고값)
}
DEFAULT_VALUES = {c: dict(zip(_DV_KEYS, row)) for c, row in _DV_ROWS.items()}
ORIGINS = list(DEFAULT_VALUES) + ["EU"]

# Column A (공정 단계 benchmark) — 실측 사용 시 자체 생산 공정에 적용
COLUMN_A = {
    "sinter": 0.086,
    "pig_iron": 1.089,
    "dri": 0.295,
    "crude": {"C": 0.188, "D": 0.065, "E": 0.065},   # 7207 12 10
    "hrc": 0.044,                                     # 7208
}
# Column B (전 공정) — 제품을 기본값으로 낼 때와 비교용
COLUMN_B_PRODUCT = {
    "7208": {"C": 1.370, "D": 0.481, "E": 0.072},
    "7207": {"C": 1.364, "D": 0.475, "E": 0.066},
}
KR_DEFAULT_PRODUCT = {"7208": 2.118, "7207": 2.118}   # 한국 기본값 (경로 C)


def _num(x, default=0.0) -> float:
    """빈칸·NaN·None → default."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(v) else v


def default_see(item: str, origin: str) -> float | None:
    """전구체 국가 기본값 (mark-up 전). EU 산은 0, '-'는 기타국가 값."""
    if origin == "EU":
        return 0.0
    v = DEFAULT_VALUES.get(origin, DEFAULT_VALUES["원산지 불명"]).get(item)
    return DEFAULT_VALUES["기타국가"][item] if v is None else v


def column_b(item: str, year: int) -> float:
    vals = PRECURSORS[item][2]
    if None in vals:
        return vals[None]
    return vals["1"] if year <= 2027 else vals["2"]


def steel_markup(year: int) -> float:
    """철강 기본값 mark-up (%) — IR 2025/2621: 2026 10, 2027 20, 2028~ 30."""
    if year <= 2026:
        return 10.0
    return 20.0 if year == 2027 else 30.0


# ── 배출 계산 ────────────────────────────────────────────────────────────────
def mass_balance(rows) -> tuple[float, list[dict]]:
    """물질수지 직접배출 [t CO₂].

    rows: dict 목록 — material(키), qty(양), factor(t CO₂/단위, 비면 기본), bio(바이오 비율 %)
    산출 물질은 음수로 들어간다 (Annex II B.3.2). 바이오 비율만큼 투입 배출을 0으로 본다.
    """
    total, detail = 0.0, []
    for r in rows:
        key = r.get("material")
        if key not in MATERIALS:
            continue
        qty = _num(r.get("qty"))
        if qty == 0:
            continue
        factor = _num(r.get("factor"), MATERIALS[key][2])
        sign = -1.0 if key in OUTPUT_KEYS else 1.0
        bio = 0.0 if sign < 0 else min(max(_num(r.get("bio")), 0.0), 100.0) / 100.0
        em = sign * abs(qty) * factor * (1.0 - bio)
        total += em
        detail.append({"key": key, "label": material_label(key), "qty": qty,
                       "factor": factor, "bio_pct": bio * 100, "em": em})
    return total, detail


def waste_gas_correction(exported_gj: float = 0.0, imported_gj: float = 0.0) -> tuple[float, float]:
    """폐가스 보정 [t CO₂] — (수입분 +, 수출분 −). 식 53·54, 에너지(NCV 기준) GJ 입력."""
    imp = _num(imported_gj) / 1000.0 * EF_NG
    exp = _num(exported_gj) / 1000.0 * EF_NG * WG_EXPORT_CORR
    return imp, -exp


def attributed_emissions(dir_em: float, heat_imp_gj=0.0, heat_exp_gj=0.0,
                         ef_heat=EF_HEAT_DEFAULT, wg_exported_gj=0.0, wg_imported_gj=0.0,
                         em_el_prod=0.0) -> dict:
    """귀속배출 AttrEm (식 55) — 음수면 0."""
    h_imp = _num(heat_imp_gj) / 1000.0 * _num(ef_heat, EF_HEAT_DEFAULT)
    h_exp = _num(heat_exp_gj) / 1000.0 * _num(ef_heat, EF_HEAT_DEFAULT)
    wg_imp, wg_exp = waste_gas_correction(wg_exported_gj, wg_imported_gj)
    raw = dir_em + h_imp - h_exp + wg_imp + wg_exp - _num(em_el_prod)
    return {"dir_em": dir_em, "heat_imp": h_imp, "heat_exp": -h_exp,
            "wg_imp": wg_imp, "wg_exp": wg_exp, "el_prod": -_num(em_el_prod),
            "attr_em": max(0.0, raw)}


def precursor_lines(rows, year: int) -> list[dict]:
    """구매 전구체 — 실측 SEE 없으면 국가 기본값 × (1 + mark-up), SEFA 없으면 Column B (EU 산 0)."""
    out = []
    mu = steel_markup(year)
    for r in rows:
        item = r.get("item")
        if item not in PRECURSORS:
            continue
        qty = _num(r.get("qty"))
        if qty <= 0:
            continue
        origin = r.get("origin") or "원산지 불명"
        see_in = r.get("see")
        actual = not (see_in is None or (isinstance(see_in, float) and math.isnan(see_in))
                      or str(see_in).strip() == "")
        if actual:
            see = _num(see_in)
            basis = "실측"
        else:
            base = default_see(item, origin)
            see = base * (1.0 + mu / 100.0)
            basis = "EU 산 0" if origin == "EU" else f"기본값 {base:.3f} + mark-up {mu:.0f}%"
        sefa_in = r.get("sefa")
        if origin == "EU":
            sefa = 0.0
        elif sefa_in is not None and str(sefa_in).strip() != "" and not (
                isinstance(sefa_in, float) and math.isnan(sefa_in)):
            sefa = _num(sefa_in)
        else:
            sefa = column_b(item, year)
        carbon = _num(r.get("carbon"), PRECURSORS[item][1])
        out.append({"item": item, "label": PRECURSORS[item][0], "origin": origin, "qty": qty,
                    "see": see, "see_basis": basis, "sefa": sefa, "carbon": carbon,
                    "embedded": qty * see, "carbon_em": qty * carbon})
    return out


def see_complex(attr_em: float, precursors_embedded: float, al: float) -> float:
    """SEE = (AttrEm + Σ M_i × SEE_i) / AL (식 59)."""
    if al <= 0:
        raise ValueError("판매 가능 생산량(AL)은 0보다 커야 합니다")
    return (attr_em + precursors_embedded) / al


def sefa_basis(product: str, route: str, al: float, own: dict, purchased: list[dict]) -> float:
    """실측 사용 시 공제 benchmark [t CO₂/t] (CBAM factor·CSCF 곱하기 전).

    = 제품 공정 Column A + Σ (자체 생산 중간재 사용량 / AL) × Column A + Σ (구매 전구체량 / AL) × SEFA_i
    own: 'crude'·'pig_iron'·'sinter'·'dri' — 연간 자체 생산분 사용량 (t). 가이던스 No.4 3.3 재귀식을
    연간 사용량으로 펼친 것과 같다.
    """
    if al <= 0:
        raise ValueError("판매 가능 생산량(AL)은 0보다 커야 합니다")
    if product == "7208":
        total = COLUMN_A["hrc"] + _num(own.get("crude")) / al * COLUMN_A["crude"][route]
    else:   # 슬래브가 최종 제품
        total = COLUMN_A["crude"][route]
    for k in ("pig_iron", "sinter", "dri"):
        total += _num(own.get(k)) / al * COLUMN_A[k]
    total += sum(p["qty"] * p["sefa"] for p in purchased) / al
    return total


def calc_bubble(*, product: str, route: str, al: float, year: int, materials, precursors,
                wg_exported_gj=0.0, wg_imported_gj=0.0, heat_imp_gj=0.0, heat_exp_gj=0.0,
                ef_heat=EF_HEAT_DEFAULT, em_el_prod=0.0, sinter_mwh=0.0, grid_ef=KR_GRID_EF,
                own=None) -> dict:
    """설치 통합(bubble) 방식 전체 계산."""
    dir_mb, mb_detail = mass_balance(materials)
    pre = precursor_lines(precursors, year)
    # 구매 전구체가 가져온 탄소도 물질수지 투입에 들어간다 (Annex I 3.14–3.15)
    pre_carbon = sum(p["carbon_em"] for p in pre)
    attr = attributed_emissions(dir_mb + pre_carbon, heat_imp_gj, heat_exp_gj, ef_heat,
                                wg_exported_gj, wg_imported_gj, em_el_prod)
    # 소결광만 간접배출 포함 (MA Art. 3(2), Annex I 3.1) — 자체 소결 전력 × 전력 배출계수
    sinter_indirect = _num(sinter_mwh) * _num(grid_ef, KR_GRID_EF) if route == "C" else 0.0
    embedded_pre = sum(p["embedded"] for p in pre)
    see_direct = see_complex(attr["attr_em"], embedded_pre, al)
    see_total = see_direct + sinter_indirect / al
    basis = sefa_basis(product, route, al, own or {}, pre)
    return {
        "see": see_total, "see_direct": see_direct, "sinter_indirect": sinter_indirect,
        "dir_mass_balance": dir_mb, "precursor_carbon": pre_carbon, "attr": attr,
        "precursors": pre, "precursor_embedded": embedded_pre,
        "materials": mb_detail, "sefa_basis": basis, "al": al,
        "product": product, "route": route, "year": year,
    }


def contributions(res: dict) -> list[tuple[str, float]]:
    """결과를 제품 1t당 항목별 기여 [t CO₂/t]로 정리 (차트용)."""
    al = res["al"]
    items = [(d["label"].split(" (")[0], d["em"] / al) for d in res["materials"]]
    if res["precursor_carbon"]:
        items.append(("구매 전구체 탄소", res["precursor_carbon"] / al))
    a = res["attr"]
    for key, name in (("wg_exp", "폐가스 수출 보정"), ("wg_imp", "폐가스 수입 보정"),
                      ("heat_imp", "열 수입"), ("heat_exp", "열 수출"), ("el_prod", "자체 발전 차감")):
        if a[key]:
            items.append((name, a[key] / al))
    for p in res["precursors"]:
        items.append((f"전구체: {p['label'].split(' (')[0]} ({p['origin']})", p["embedded"] / al))
    if res["sinter_indirect"]:
        items.append(("소결 간접배출", res["sinter_indirect"] / al))
    return items


# ── 화면 첫 표시용 예시 (가상) ─────────────────────────────────────────────────
# 경로 C: 집행위 가이던스 5d 예시 1 (한국 소재 가상 일관제철소, 표 4-1~4-6)
#   → 직접 SEE 1.539, 소결 간접 포함 1.567, 열연 SEFA 기준 1.248
EXAMPLES = {
    "C": {
        "al": 4_800_000,
        "materials": [
            ("coke_breeze", 50_000, 0.88 * C_TO_CO2, 0),
            ("iron_ore", 5_600_000, 0.00023 * C_TO_CO2, 0),
            ("coke", 2_200_000, 0.88 * C_TO_CO2, 0),
            ("plastic_waste", 70_000, 0.684 * C_TO_CO2, 16),
            ("steel_scrap", 1_000_000, 0.00204 * C_TO_CO2, 0),
            ("lime", 280_000, 0.00273 * C_TO_CO2, 0),
            ("natural_gas_t", 170_000, 0.75 * C_TO_CO2, 0),
            ("other_in", 40_000, 0.10 * C_TO_CO2, 0),
            ("steel_out", 4_800_000, 0.0018 * C_TO_CO2, 0),
            ("slag_out", 1_000_000, 0.0003 * C_TO_CO2, 0),
        ],
        "wg_exported_gj": 12_800_000,
        "sinter_mwh": 241_111,
        "grid_ef": 132_797 / 241_111,   # 예시의 자가발전·계통 가중 배출계수
        "own": {"crude": 5_001_600, "pig_iron": 4_001_280, "sinter": 5_601_792},
        "note": "집행위 가이던스 No.5d 예시 1 (한국 소재 가상 일관제철소, 탄소함량은 예시값).",
    },
    "D": {
        "al": 1_000_000,
        "materials": [
            ("natural_gas", 12_400_000, None, 0),
            ("charge_carbon", 10_000, None, 0),
            ("electrode", 1_500, None, 0),
            ("steel_scrap", 200_000, None, 0),
            ("steel_out", 1_000_000, None, 0),
        ],
        "own": {"crude": 1_042_000, "dri": 1_000_000},
        "note": "가상 수치 (DRI 환원·전기로·가열로 천연가스 12.4 GJ/t). 회사 자료로 바꾸세요.",
    },
    "E": {
        "al": 1_000_000,
        "materials": [
            ("charge_carbon", 15_000, None, 0),
            ("electrode", 1_500, None, 0),
            ("steel_scrap", 1_100_000, None, 0),
            ("natural_gas", 1_920_000, None, 0),
            ("steel_out", 1_050_000, None, 0),
        ],
        "own": {"crude": 1_042_000},
        "note": "가상 수치 (설계안 §7 예시, 열연 1t당). 회사 자료로 바꾸세요.",
    },
}
