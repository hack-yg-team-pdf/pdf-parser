import sys
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1
from pdfminer.pdfpage import PDFPage
from PIL import Image, ImageDraw
from pdf2image import convert_from_path
import numpy as np

filename = 'decrypted_pdfs/2.pdf'
fp = open(filename, 'rb')

images = convert_from_path(filename)

parser = PDFParser(fp)
doc = PDFDocument(parser)

pdfImages = {}
for i, pdfPage in enumerate(PDFPage.create_pages(doc)):
    pdfImages[pdfPage.pageid] = (images[i], images[i].copy())

fields = resolve1(doc.catalog['AcroForm'])['Fields']
for field in fields:
    resolved_field = resolve1(field)
    name, value, rect, page_id = resolved_field.get('T'), resolved_field.get('V'), resolved_field.get('Rect'), resolved_field.get('P')
    # PDF Rect comes in format

    if page_id is None:
        continue

    page_resolved = resolve1(page_id)
    draw_image = pdfImages[page_id.objid][1].copy()
    composite_image = pdfImages[page_id.objid][0]

    image_height = draw_image.height
    image_width = draw_image.width

    page_width = page_resolved['MediaBox'][2]
    page_height = page_resolved['MediaBox'][3]

    scale = image_height / page_height

    print('{0}: {1}, {2}'.format(name, value, rect))

    x0 = rect[0] * scale
    y0 = image_height - rect[1] * scale
    x1 = rect[2] * scale
    y1 = image_height - rect[3] * scale
    # [(x0, y0), (x1, y1)] or [x0, y0, x1, y1]

    draw1 = ImageDraw.Draw(draw_image, 'RGBA')
    draw1.rectangle([x0, y0, x1, y1], fill=(0,0,250, 100))

    draw2 = ImageDraw.Draw(composite_image, 'RGBA')
    draw2.rectangle([x0, y0, x1, y1], fill=(0,0,250, 100))

    # cropped = img.crop( ( x, y, x + width , y + height ) )
    crop_area = (x0-300, y1-200, x1+300, y0+200)

    cropped_example = draw_image.crop(crop_area)

    output_file_name = "d_" + str(field.objid) + ".png"
    cropped_example.save('mturk_images/' + output_file_name, "PNG")

for pdfImage in pdfImages:
    pdfImages[pdfImage][0].show()