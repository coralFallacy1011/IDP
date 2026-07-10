"""Quick smoke test for newly added services.
Run this from the project root with the virtualenv activated.
"""
from services.classification_service import classify
from services.metadata_service import extract_metadata
from services.summarization_service import summarize


SAMPLE_TEXT = """
FIR No: 1234/2023
Date: 2023-05-10
Complaint filed by: Ravi Kumar, resident of 12 MG Road, Bengaluru.
Accused: Unknown persons. IPC Sections: 302, 307.
This is a complaint regarding theft and assault near the market area.
"""


def main():
    print("=== SAMPLE TEXT ===")
    print(SAMPLE_TEXT)

    print("\n=== CLASSIFICATION ===")
    c = classify(SAMPLE_TEXT)
    print(c)

    print("\n=== METADATA ===")
    m = extract_metadata(SAMPLE_TEXT)
    print(m)

    print("\n=== SUMMARIZATION ===")
    s = summarize(SAMPLE_TEXT)
    print(s)


if __name__ == '__main__':
    main()
