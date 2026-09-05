"""Chapter-wise exam weightage data, so PaperBanao can show teachers which
chapters carry the most marks in the actual board exam — something a
generic AI question-paper tool has no reason to know, since it requires
real research into each board's exam pattern, not just the syllabus list.

This is a proof-of-concept covering ONE subject/class combination for now
(BSEB Class 10 Mathematics). The data below reflects the BSEB Class 10 Math
exam's unit-wise mark distribution (100 marks total, 7 units), sourced from
published exam-pattern references and cross-checked across multiple
sources. Expanding this to more subjects/classes is a bigger undertaking
(each one needs its own research) — a good next step once there's time to
invest in it properly, but deliberately out of scope for this first pass.
"""

# Unit-wise total marks for BSEB Class 10 Mathematics (100 marks total).
_BSEB_CLASS10_MATH_UNIT_MARKS = {
    "Number System": 10,
    "Algebra": 20,
    "Coordinate Geometry": 10,
    "Trigonometry": 20,
    "Geometry": 20,
    "Mensuration": 10,
    "Statistics & Probability": 10,
}

# Which chapters fall under which unit, using standard NCERT/BSEB Class 10
# Math chapter names.
_BSEB_CLASS10_MATH_CHAPTER_UNITS = {
    "real numbers": "Number System",
    "polynomials": "Algebra",
    "pair of linear equations in two variables": "Algebra",
    "quadratic equations": "Algebra",
    "arithmetic progressions": "Algebra",
    "coordinate geometry": "Coordinate Geometry",
    "introduction to trigonometry": "Trigonometry",
    "some applications of trigonometry": "Trigonometry",
    "triangles": "Geometry",
    "circles": "Geometry",
    "constructions": "Geometry",
    "areas related to circles": "Mensuration",
    "surface areas and volumes": "Mensuration",
    "statistics": "Statistics & Probability",
    "probability": "Statistics & Probability",
}

# Registry of which (class, subject) combinations have weightage data —
# add more entries here as more subjects get researched.
WEIGHTAGE_DATA = {
    ("class 10", "mathematics"): (_BSEB_CLASS10_MATH_CHAPTER_UNITS, _BSEB_CLASS10_MATH_UNIT_MARKS),
}


def get_chapter_weightage(class_name: str, subject_name: str, chapters: list[str]):
    """Given a list of chapter names (as actually stored/typed for this
    teacher's curriculum), returns weightage info for any that match our
    known data. Matching is case-insensitive since teachers may have typed
    chapter names with different capitalization. Chapters we have no data
    for are simply omitted from the result — this is meant to enhance the
    UI when data is available, not require it everywhere."""
    key = (class_name.strip().lower(), subject_name.strip().lower())
    if key not in WEIGHTAGE_DATA:
        return {}

    chapter_units, unit_marks = WEIGHTAGE_DATA[key]
    result = {}
    for chapter in chapters:
        unit = chapter_units.get(chapter.strip().lower())
        if unit:
            marks = unit_marks[unit]
            result[chapter] = {
                "unit": unit,
                "unit_marks": marks,
                "priority": "high" if marks >= 20 else "standard",
            }
    return result
