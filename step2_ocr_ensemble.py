#!/usr/bin/env python3
"""
LedgerLinc Step 2: OCR + Field Extraction + Structuring Pipeline
Supports single PDF, single image, or folder of images.
"""

import argparse
import json
from pathlib import Path
from datetime import datetime

from PIL import Image
import cv2
from paddleocr import PaddleOCR, PPStructure

# For future VLM ensemble (Qwen3-VL, Gemma 4, Falcon OCR)
# We'll stub them for now so the script runs on CPU in Codespaces

def load_document(input_path: str):
    path = Path(input_path)
    if path.is_dir():
        images = [Image.open(f) for f in path.glob("*.png") | path.glob("*.jpg") | path.glob("*.jpeg")]
        return images
    elif path.suffix.lower() == ".pdf":
        # Simple PDF to images (using pdf2image would be better, but we keep deps light)
        print("PDF support coming soon - for now please provide image files")
        return []
    else:
        return [Image.open(path)]

def run_paddle_ocr(images):
    ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
    structure = PPStructure(use_gpu=False, show_log=False)
    
    results = []
    for img in images:
        # Layout analysis
        layout = structure(img)
        # Text OCR
        ocr_result = ocr.ocr(img, cls=True)
        results.append({
            "layout": layout,
            "ocr_text": "\n".join([line[1][0] for line in ocr_result[0]]) if ocr_result and ocr_result[0] else ""
        })
    return results

def create_structured_output(paddle_results, doc_id: str, client_id: str = "test"):
    # Stub for VLM ensemble - replace with real Qwen3-VL call later
    structured = {
        "doc_id": doc_id,
        "client_id": client_id,
        "processed_timestamp": datetime.utcnow().isoformat(),
        "document_type": "invoice",  # TODO: make dynamic
        "vendor_candidate": {
            "company_name": "Unknown Vendor",
            "address_lines": [],
            "tax_id": None,
            "website": None
        },
        "key_fields": {
            "invoice_number": None,
            "invoice_date": None,
            "total_amount": None,
            "currency": "USD",
            "line_items": []
        },
        "confidence_scores": {
            "company_name": 0.65,
            "tax_id": 0.40
        },
        "flags": ["needs_vlm_refinement"]
    }
    return structured

def main():
    parser = argparse.ArgumentParser(description="LedgerLinc Step 2 OCR Pipeline")
    parser.add_argument("--input", required=True, help="Path to image, PDF, or folder of images")
    parser.add_argument("--client_id", default="test", help="Client ID")
    args = parser.parse_args()

    print(f"Processing: {args.input}")

    images = load_document(args.input)
    if not images:
        print("No images loaded.")
        return

    paddle_results = run_paddle_ocr(images)
    
    output = create_structured_output(paddle_results, doc_id=Path(args.input).stem, client_id=args.client_id)

    # Save output
    output_path = Path("output") / f"{Path(args.input).stem}_structured.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Step 2 completed. Output saved to: {output_path}")
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
