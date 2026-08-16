"""
Run this ONCE before the first trial to generate the 3 seed PDFs for Task 2.
Requires: pip install fpdf2

Run it from inside this folder (templates/seeds/task2A/). It writes the PDFs
here and mirrors them into ../task2B/ automatically. The PDFs are generated
rather than committed so the repo carries no binaries -- regenerating them is
deterministic, so every reproduction gets byte-identical seeds.
"""

try:
    from fpdf import FPDF
except ImportError:
    raise SystemExit("Run: pip install fpdf2")

BOOKS = [
    {
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "year": "2008",
        "pages": "431",
        "summary": "A handbook of agile software craftsmanship covering naming, functions, and refactoring."
    },
    {
        "title": "The Pragmatic Programmer",
        "author": "Andrew Hunt and David Thomas",
        "year": "1999",
        "pages": "352",
        "summary": "Timeless advice on software development practices, tools, and mindset."
    },
    {
        "title": "Structure and Interpretation of Computer Programs",
        "author": "Harold Abelson and Gerald Jay Sussman",
        "year": "1996",
        "pages": "657",
        "summary": "Classic MIT textbook on computational thinking using Scheme."
    },
]

import os, shutil

for book in BOOKS:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=16)
    pdf.cell(0, 12, book["title"], ln=True)
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, f"Author: {book['author']}", ln=True)
    pdf.cell(0, 10, f"Year: {book['year']}", ln=True)
    pdf.cell(0, 10, f"Pages: {book['pages']}", ln=True)
    pdf.multi_cell(0, 10, f"Summary: {book['summary']}")

    fname = book["title"].replace(" ", "_").replace("/", "-") + ".pdf"
    out_a = os.path.join(os.path.dirname(__file__), fname)
    pdf.output(out_a)

    # Mirror to task2B seeds
    out_b = out_a.replace("task2A", "task2B")
    os.makedirs(os.path.dirname(out_b), exist_ok=True)
    shutil.copy(out_a, out_b)
    print(f"Created: {fname}")

print("Done — PDFs written to task2A/ and task2B/ seed dirs.")
