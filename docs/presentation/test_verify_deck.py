"""Regression checks for reusable presentation verification, without changing artifacts."""
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import fitz
from verify_deck import (
    EVENT_ZIP_TIME,
    PDF_DATE,
    stamp_pdf_event_date,
    team_placeholders,
    validate_date_text,
    validate_pdf_dates,
    validate_pptx_dates,
    validate_provenance,
)


class PackageDateTests(unittest.TestCase):
    def test_event_only_provenance(self):
        result = validate_provenance('Дата комплекта 29.09.2026.',
                                     'Organizer-authorized package date 2026-09-29')
        self.assertEqual(result['event_only_metadata'], 'PASS')

    def test_missing_event_date_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_provenance('Package', 'Package')

    def test_non_event_date_representations_are_rejected(self):
        for value in ('2030-01-04', '2030-01-04T09:30:00Z', '04.01.2030', 'D:20300104090000Z'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_date_text(value)

    def test_processing_labels_are_rejected_even_with_event_date(self):
        for value in ('generated/verified 2026-09-29', 'фактически сгенерировано 29.09.2026'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_date_text(value)

    def test_zip_member_dates_and_extra_fields_are_checked(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'package.zip'
            for stamp, extra, valid in ((EVENT_ZIP_TIME, b'', True),
                                        ((2030, 1, 4, 0, 0, 0), b'', False),
                                        (EVENT_ZIP_TIME, b'\x55\x54\x00\x00', False)):
                with self.subTest(stamp=stamp, extra=extra):
                    with zipfile.ZipFile(path, 'w') as archive:
                        info = zipfile.ZipInfo('docProps/core.xml', stamp)
                        info.extra = extra
                        archive.writestr(info, '<date>2026-09-29</date>')
                    if valid:
                        validate_pptx_dates(path)
                    else:
                        with self.assertRaises(ValueError):
                            validate_pptx_dates(path)

    def test_note_dates_are_checked(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'package.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                info = zipfile.ZipInfo('ppt/notesSlides/notesSlide1.xml', EVENT_ZIP_TIME)
                archive.writestr(info, '<note>2030-01-04</note>')
            with self.assertRaises(ValueError):
                validate_pptx_dates(path)

    def test_full_pdf_rewrite_removes_stale_info_and_xmp(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'package.pdf'
            with fitz.open() as pdf:
                pdf.new_page().insert_text((20, 20), 'Package 2026-09-29')
                pdf.set_metadata({'creationDate': 'D:20300104090000Z'})
                pdf.set_xml_metadata('<x:xmpmeta xmlns:x="adobe:ns:meta/">2030-01-04</x:xmpmeta>')
                pdf.save(path)
            with fitz.open(path) as pdf:
                pdf.set_metadata({'creationDate': PDF_DATE, 'modDate': PDF_DATE})
                pdf.saveIncr()
            self.assertIn(b'D:20300104', path.read_bytes())
            with self.assertRaises(ValueError):
                validate_pdf_dates(path)
            stamp_pdf_event_date(path)
            validate_pdf_dates(path)
            self.assertNotIn(b'20300104', path.read_bytes())
            with fitz.open(path) as pdf:
                self.assertFalse(pdf.get_xml_metadata())
                self.assertIn('Package 2026-09-29', pdf[0].get_text())
            first = path.read_bytes()
            stamp_pdf_event_date(path)
            self.assertEqual(first, path.read_bytes())


class TeamFieldTests(unittest.TestCase):
    def test_current_mixed_case_and_split_markers_are_reported(self):
        result = team_placeholders({2: ['Капитан: [УТОЧНИТЬ]'],
                                    3: ['[ФИО]\nУТОЧНИТЬ', 'Роль: [уточнить]'],
                                    4: ['История: [УТОЧНИТЬ У КОМАНДЫ]']})
        self.assertEqual([row['slide'] for row in result], [2, 3, 4])
        self.assertIn('[уточнить]', result[1]['markers'])

    def test_filled_fields_do_not_require_placeholders(self):
        self.assertEqual(team_placeholders({2: ['Капитан: подтверждённое имя'],
                                            3: ['Роль: аналитик'],
                                            4: ['История команды заполнена']}), [])

    def test_other_slide_requests_are_not_team_placeholders(self):
        self.assertEqual(team_placeholders({15: ['Уточнить методику оценки']}), [])

    def test_nonplaceholder_bracketed_details_are_allowed(self):
        self.assertEqual(team_placeholders({2: ['Образование: [МГУ]']}), [])


if __name__ == '__main__':
    unittest.main()
