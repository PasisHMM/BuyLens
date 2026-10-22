import pytest

from app.pipeline.extract.sizechart import find_size_chart
from app.pipeline.extract.text import soup_of


def chart(html: str):
    result = find_size_chart(soup_of(html))
    assert result is not None
    return {r.label: {d: (m.cm, m.basis) for d, m in r.measures.items()} for r in result.rows}


def test_size_per_row_inches_body_default():
    rows = chart("""
        <h3>Size guide (inches)</h3>
        <table><tr><th>Size</th><th>Waist</th><th>Hip</th></tr>
        <tr><td>26</td><td>26</td><td>36</td></tr><tr><td>27</td><td>27</td><td>37</td></tr></table>
    """)
    assert rows["26"] == {"waist": (66.0, "body"), "hips": (91.4, "body")}


def test_size_per_column_cm():
    rows = chart("""
        <table><tr><th></th><th>S</th><th>M</th><th>L</th></tr>
        <tr><td>Waist (cm)</td><td>66</td><td>71</td><td>76</td></tr>
        <tr><td>Inseam (cm)</td><td>76</td><td>76</td><td>78</td></tr></table>
    """)
    assert rows["M"] == {"waist": (71.0, "body"), "inseam": (76.0, "body")}


def test_ranges_and_halves():
    rows = chart("""
        <table><tr><th>Size</th><th>Waist (in)</th><th>Hips (in)</th></tr>
        <tr><td>S</td><td>26-27</td><td>36½</td></tr><tr><td>M</td><td>28 &ndash; 29</td><td>38 1/2</td></tr></table>
    """)
    assert rows["S"]["waist"][0] == pytest.approx(26.5 * 2.54, abs=0.1)
    assert rows["S"]["hips"][0] == pytest.approx(36.5 * 2.54, abs=0.1)
    assert rows["M"]["hips"][0] == pytest.approx(38.5 * 2.54, abs=0.1)


def test_garment_measured_flat_is_doubled():
    rows = chart("""
        <p>Garment measurements, laid flat (inches)</p>
        <table><tr><th>Size</th><th>Waist</th></tr><tr><td>26</td><td>13.5</td></tr><tr><td>27</td><td>14</td></tr></table>
    """)
    assert rows["26"]["waist"] == (round(27 * 2.54, 1), "garment")


def test_unlabeled_unit_is_inferred_only_when_unambiguous():
    rows = chart("""
        <table><tr><th>Size</th><th>Waist</th><th>Inseam</th></tr>
        <tr><td>26</td><td>66</td><td>76</td></tr><tr><td>27</td><td>69</td><td>76</td></tr></table>
    """)
    assert rows["26"]["waist"][0] == 66.0  # 66 can only be cm for a waist


def test_ignores_unrelated_tables():
    html = "<table><tr><th>Shipping</th><th>Cost</th></tr><tr><td>Standard</td><td>$5</td></tr></table>"
    assert find_size_chart(soup_of(html)) is None
