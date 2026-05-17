from pathlib import Path


def test_ac2_byte_identical_rerun(tmp_path, us1_source_pdf):
    import shutil

    from dartwing_ocr.preprocessing import pipeline

    folder_a = tmp_path / "run_a" / "inv_001"
    folder_b = tmp_path / "run_b" / "inv_001"
    folder_a.mkdir(parents=True)
    folder_b.mkdir(parents=True)
    shutil.copy(us1_source_pdf, folder_a / "source.pdf")
    shutil.copy(us1_source_pdf, folder_b / "source.pdf")

    out_a = pipeline.run(pipeline.Invocation(document_folder=folder_a))
    out_b = pipeline.run(pipeline.Invocation(document_folder=folder_b))

    bytes_a = Path(out_a).read_bytes()
    bytes_b = Path(out_b).read_bytes()
    assert bytes_a == bytes_b, "preprocess_output.json must be byte-identical across reruns"
