import unittest
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch, AsyncMock
from infrastructure.document.contract_parser import validate_file, parse_contract


class ParserTests(unittest.TestCase):
    def test_rejects_empty_fake_and_unsupported_uploads(self):
        for name, data in [('x.pdf', b''), ('x.pdf', b'not a pdf'), ('x.docx', b'PKfake'), ('x.exe', b'%PDF-')]:
            with self.subTest(name=name, data=data), self.assertRaises(ValueError):
                validate_file(name, data)

    def test_docx_keeps_paragraph_and_table_order(self):
        from docx import Document
        document = Document()
        document.add_paragraph('采购合同')
        document.add_table(rows=1, cols=1).cell(0, 0).text = '金额：100 元'
        document.add_paragraph('期限：一年')
        stream = BytesIO(); document.save(stream)
        text = parse_contract('test.docx', stream.getvalue())
        self.assertLess(text.index('采购合同'), text.index('金额'))
        self.assertLess(text.index('金额'), text.index('期限'))

    def test_scan_pdf_is_not_reported_as_success(self):
        from fpdf import FPDF
        pdf = FPDF(); pdf.add_page()
        with self.assertRaisesRegex(ValueError, '扫描件'):
            parse_contract('scan.pdf', bytes(pdf.output()))

    def test_zip_without_document_is_rejected(self):
        stream = BytesIO()
        with ZipFile(stream, 'w') as archive:
            archive.writestr('random.txt', 'hello')
        with self.assertRaises(ValueError):
            validate_file('file.docx', stream.getvalue())

    def test_long_contract_is_rejected_instead_of_truncated(self):
        from docx import Document
        document = Document(); document.add_paragraph('A' * 80001)
        stream = BytesIO(); document.save(stream)
        with self.assertRaisesRegex(ValueError, '未进行截断'):
            parse_contract('long.docx', stream.getvalue())


class ReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_fabricated_evidence_is_rejected(self):
        from products.contract.application.analysis import review_document
        from products.contract.schemas.analysis import ContractAnalysis, Risk
        result = ContractAnalysis(document_type='合同', summary='摘要', risks=[Risk(
            title='风险', risk_level='high', original_text='不存在的条款', reason='原因', suggestion='建议')])
        with self.assertRaisesRegex(ValueError, '引用原文'):
            await review_document('真实条款', AsyncMock(return_value=result))

    async def test_valid_evidence_is_accepted(self):
        from products.contract.application.analysis import review_document
        from products.contract.schemas.analysis import ContractAnalysis, Risk
        result = ContractAnalysis(document_type='合同', summary='摘要', risks=[Risk(
            title='风险', risk_level='high', original_text='真实条款', reason='原因', suggestion='建议')])
        self.assertEqual(await review_document('真实 条款', AsyncMock(return_value=result)), result)


if __name__ == '__main__':
    unittest.main()
