import pymupdf as fitz
import pytest

from ja_translator.project import Project, sidecar_path
from ja_translator.translate import FakeTranslator, needs_translation


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.draw_rect(fitz.Rect(0, 0, 400, 60), color=None, fill=(0.1, 0.3, 0.6))
    page.insert_text((20, 40), "Quarterly Sales Report", fontname="helv", fontsize=22, color=(1, 1, 1))
    page.insert_textbox(
        fitz.Rect(20, 90, 380, 160),
        "Revenue grew by twelve percent compared with the previous year.",
        fontname="helv",
        fontsize=12,
    )
    page.draw_line((20, 200), (380, 200), color=(0, 0, 0))
    page.insert_text((20, 230), "Contact the team for details", fontname="helv", fontsize=11)
    doc.save(path)
    doc.close()
    return path


def test_only_english_text_is_extracted(sample_pdf):
    units = Project.open(sample_pdf).units
    assert [u.source for u in units] == [
        "Quarterly Sales Report",
        "Revenue grew by twelve percent compared with the previous year.",
        "Contact the team for details",
    ]


def test_numbers_only_are_not_translated():
    assert not needs_translation("2026")
    assert not needs_translation("12%")
    assert needs_translation("Hello world")


def test_export_replaces_text_and_keeps_background(sample_pdf, tmp_path):
    project = Project.open(sample_pdf)
    for unit, ja in zip(project.units, ["売上報告書", "前年比で12%増加しました", "詳細はチームへ"]):
        unit.translation = ja
    out = tmp_path / "out.pdf"
    project.export(out)

    page = fitz.open(out)[0]
    text = page.get_text()
    assert "Quarterly" not in text
    assert "Revenue grew" not in text
    banner = page.get_pixmap(dpi=72, clip=fitz.Rect(0, 0, 10, 10))
    red, green, blue = banner.samples[0], banner.samples[1], banner.samples[2]
    assert blue > red, "ヘッダーの青い背景は残すこと"


def test_japanese_output_is_placed_and_text_is_searchable(sample_pdf, tmp_path):
    project = Project.open(sample_pdf)
    project.units[0].translation = "売上報告書"
    project.units[2].translation = "詳細はチームへ"
    out = tmp_path / "ja.pdf"
    project.export(out)
    text = fitz.open(out)[0].get_text()
    assert "売上報告書" in text
    assert "詳細はチームへ" in text


def test_overflowing_translation_is_reported(sample_pdf):
    project = Project.open(sample_pdf)
    project.units[1].translation = "非常に長い訳文です。" * 30
    assert project.units[1].id in project.warnings()


def test_user_scale_is_respected_without_auto_shrink(sample_pdf):
    project = Project.open(sample_pdf)
    unit = project.units[1]
    unit.translation = "前年比で12%増加しました。"
    unit.scale = 1.4
    from ja_translator.model import layout_unit

    assert layout_unit(unit).size == pytest.approx(unit.size * 1.4)


def test_sidecar_restores_adjustments_when_source_is_unchanged(sample_pdf):
    project = Project.open(sample_pdf)
    project.translate(FakeTranslator(prefix=""))
    project.units[1].translation = "手で直した訳文"
    project.units[1].dx = 5.0
    project.save_sidecar()

    reopened = Project.open(sample_pdf)
    assert reopened.units[1].translation == "手で直した訳文"
    assert reopened.units[1].dx == 5.0
    sidecar_path(sample_pdf).unlink()


def test_sidecar_ignores_units_whose_source_changed(sample_pdf):
    project = Project.open(sample_pdf)
    project.translate(FakeTranslator(prefix=""))
    project.units[0].translation = "古い訳"
    project.save_sidecar()

    data = sidecar_path(sample_pdf).read_text(encoding="utf-8")
    sidecar_path(sample_pdf).write_text(data.replace("Quarterly Sales Report", "Changed title"), encoding="utf-8")
    reopened = Project.open(sample_pdf)
    assert reopened.units[0].translation is None
    sidecar_path(sample_pdf).unlink()
