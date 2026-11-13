import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.fundamental import fetch_quarterly_financials, classify_tri_factor_grade


def test_quarterly_financials_bbca():
    data = fetch_quarterly_financials("BBCA")
    assert data["available"] is True
    assert data["ticker"] == "BBCA"
    assert data["revenue"] is not None and data["revenue"] > 0
    assert data["net_income"] is not None and data["net_income"] > 0
    assert 0 <= data["f_score"] <= 9
    assert len(data["f_criteria"]) == 9
    assert len(data["historical_quarters"]) >= 4

    grade = classify_tri_factor_grade("BBCA", data, cmf_value=0.08)
    assert grade["grade"] in ["A", "B", "C", "D"]
    assert "GRADE" in grade["badge"]


def test_quarterly_financials_ptba():
    data = fetch_quarterly_financials("PTBA")
    assert data["available"] is True
    assert data["ticker"] == "PTBA"
    assert 0 <= data["f_score"] <= 9
    assert len(data["f_criteria"]) == 9
    assert data["revenue_yoy_pct"] is not None

    grade = classify_tri_factor_grade("PTBA", data, cmf_value=-0.02)
    assert grade["grade"] in ["A", "B", "C", "D"]


def test_quarterly_financials_kota():
    data = fetch_quarterly_financials("KOTA")
    assert data["available"] is True
    assert data["ticker"] == "KOTA"
    assert 0 <= data["f_score"] <= 9
    assert "quality_status" in data


def test_tri_factor_classifier_edge_cases():
    empty_data = {"available": False, "f_score": 0}
    gr_empty = classify_tri_factor_grade("XYZ", empty_data)
    assert gr_empty["grade"] == "C"

    toxic_data = {"available": True, "f_score": 2, "quality_status": "NEGATIVE_CFO"}
    gr_toxic = classify_tri_factor_grade("TOXIC", toxic_data, cmf_value=-0.12)
    assert gr_toxic["grade"] == "D"
    assert gr_toxic["color"] == "#ef4444"


if __name__ == "__main__":
    test_quarterly_financials_bbca()
    test_quarterly_financials_ptba()
    test_quarterly_financials_kota()
    test_tri_factor_classifier_edge_cases()
    print("All tests passed successfully!")
