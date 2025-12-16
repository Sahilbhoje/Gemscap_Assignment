import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: extract_pdf_text.py <pdf_path> [output_txt]")
        sys.exit(1)
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        sys.exit(2)

    try:
        from pypdf import PdfReader
    except Exception as e:
        print(f"Failed to import pypdf: {e}")
        sys.exit(3)

    reader = PdfReader(str(pdf_path))
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        if txt and not txt.endswith("\n"):
            txt += "\n"
        parts.append(txt + ("\n" if i < len(reader.pages) - 1 else ""))

    content = "".join(parts)
    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
        out_path.write_text(content, encoding="utf-8")
    else:
        print(content)

if __name__ == "__main__":
    main()
