"""Demo parser: retain page/paragraph labels for review and source preview."""
from io import BytesIO
from zipfile import ZipFile, BadZipFile

MAX_BYTES = 20 * 1024 * 1024
MAX_CHARS = 80000


def validate_file(filename: str, data: bytes) -> str:
    suffix = filename.lower().rsplit('.', 1)[-1]
    if not data or len(data) > MAX_BYTES:
        raise ValueError('文件为空或超过 20 MB')
    if suffix == 'pdf' and data.startswith(b'%PDF-'):
        return suffix
    if suffix == 'docx':
        try:
            with ZipFile(BytesIO(data)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError('DOCX 解压后过大')
                if 'word/document.xml' in archive.namelist():
                    return suffix
        except BadZipFile:
            pass
    raise ValueError('请上传有效的 PDF 或 DOCX 文件')


def parse_contract(filename: str, data: bytes) -> str:
    kind = validate_file(filename, data)
    if kind == 'pdf':
        import pdfplumber
        with pdfplumber.open(BytesIO(data)) as pdf:
            if len(pdf.pages) > 100:
                raise ValueError('Demo 支持最多 100 页合同')
            text = '\n\n'.join(f'[第 {i + 1} 页]\n{p.extract_text() or ""}' for i, p in enumerate(pdf.pages))
            if not any((p.extract_text() or '').strip() for p in pdf.pages):
                raise ValueError('未提取到文字；扫描件暂不支持，请上传文字版 PDF 或 DOCX')
    else:
        from docx import Document
        from docx.oxml.ns import qn
        document = Document(BytesIO(data))
        blocks = []
        for block in document.element.body:
            paragraphs = [block] if block.tag == qn('w:p') else block.findall('.//' + qn('w:p'))
            for paragraph in paragraphs:
                value = ''.join(t.text or '' for t in paragraph.findall('.//' + qn('w:t')))
                if value.strip():
                    blocks.append(value)
        text = '\n\n'.join(f'[段落 {i + 1}] {p}' for i, p in enumerate(blocks))
    if not text.strip():
        raise ValueError('文档没有可分析的文字')
    if len(text) > MAX_CHARS:
        raise ValueError('Demo 支持最多 8 万字符，请拆分合同后上传；未进行截断分析')
    return text
