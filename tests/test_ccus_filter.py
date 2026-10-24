"""CCUS 기술의 업종 적용 필터 — VPSA(고압 합성가스 전용)는 수소·비료 업종에서만 비교."""

VPSA = {"applicable_sectors": ["h2_smr"]}


def test_tech_without_restriction_applies_everywhere(calc):
    for sector in calc.CBAM_TO_CCUS_SOURCE:
        assert calc.ccus_tech_applies({}, sector)


def test_vpsa_only_for_syngas_sectors(calc):
    assert calc.ccus_tech_applies(VPSA, "hydrogen_SMR")
    assert calc.ccus_tech_applies(VPSA, "fertilizer_NH3")
    for sector in ("steel_BF_BOF", "steel_EAF", "cement", "aluminum", "power"):
        assert not calc.ccus_tech_applies(VPSA, sector), sector


def test_unknown_sector_excludes_restricted_tech(calc):
    assert not calc.ccus_tech_applies(VPSA, "unknown_sector")
