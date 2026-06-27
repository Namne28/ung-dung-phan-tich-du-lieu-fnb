import zipfile
import xml.etree.ElementTree as ET

doc = zipfile.ZipFile('Thực tập tốt nghiệp nam.docx')
xml_content = doc.read('word/document.xml')
root = ET.fromstring(xml_content)
ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
text = [node.text for node in root.findall('.//w:t', ns) if node.text]

with open('doc_content.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(text))
