import docx

doc = docx.Document('Thực tập tốt nghiệp nam.docx')
with open('doc_content2.txt', 'w', encoding='utf-8') as f:
    for p in doc.paragraphs:
        if p.text.strip():
            f.write(p.text.strip() + '\n')
