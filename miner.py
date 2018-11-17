import sys
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1
from pdfminer.pdfpage import PDFPage
from PIL import Image, ImageDraw
from pdf2image import convert_from_path
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfpage import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfdevice import PDFDevice
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
import pdfminer

from pyqtree import Index

from pdfminer.layout import LAParams, LTTextBox,LTChar, LTFigure

filename = 'decrypted_pdfs/1.pdf'
fp = open(filename, 'rb')

images = convert_from_path(filename)

parser = PDFParser(fp)
doc = PDFDocument(parser)

if not doc.is_extractable:
    raise PDFTextExtractionNotAllowed

# Create a PDF resource manager object that stores shared resources.
rsrcmgr = PDFResourceManager()

# Create a PDF device object.
device = PDFDevice(rsrcmgr)

# BEGIN LAYOUT ANALYSIS
# Set parameters for analysis.
laparams = LAParams()

# Create a PDF page aggregator object.
device = PDFPageAggregator(rsrcmgr, laparams=laparams)

# Create a PDF interpreter object.
interpreter = PDFPageInterpreter(rsrcmgr, device)

def parse_obj(lt_objs, quadtree_index):
    # loop over the object list
    for obj in lt_objs:
        # if it's a textbox, print text and location
        if isinstance(obj, pdfminer.layout.LTTextBoxHorizontal):
            quadtree_index.insert(obj, obj.bbox)
            #print("%6d, %6d, %s" % (obj.bbox[0], obj.bbox[1], obj.get_text().replace('\n', '_')))

pdfImages = {}
for i, pdfPage in enumerate(PDFPage.create_pages(doc)):
    quadtree_index = Index(bbox=(0, 0, pdfPage.mediabox[2], pdfPage.mediabox[3]))
    pdfImages[pdfPage.pageid] = (images[i], images[i].copy(), quadtree_index)

    # read the page into a layout object
    interpreter.process_page(pdfPage)
    layout = device.get_result()

    # extract text from this object
    parse_obj(layout._objs, quadtree_index)

fields = resolve1(doc.catalog['AcroForm'])['Fields']
for field in fields:
    resolved_field = resolve1(field)
    name, value, rect, page_id = resolved_field.get('T'), resolved_field.get('V'), resolved_field.get('Rect'), resolved_field.get('P')
    # PDF Rect comes in format

    is_textfield = True
    if resolved_field['FT'].name == 'Tx':
        is_textfield = True
    elif resolved_field['FT'].name == 'Btn':
        is_textfield = False
    else:
        print('weird form')

    if page_id is None:
        continue

    page_resolved = resolve1(page_id)
    draw_image = pdfImages[page_id.objid][1].copy()
    composite_image = pdfImages[page_id.objid][0]
    quadtree_index =  pdfImages[page_id.objid][2]

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

    spacer = 0
    while True:
        # keep increasing area until we grab at least one textfield
        if is_textfield:
            quadrect = [rect[0] - spacer, rect[1] - spacer, rect[2], rect[3]]
        else:
            quadrect = [rect[0], rect[1], rect[2]+ spacer, rect[3] + spacer]

        matches = quadtree_index.intersect(quadrect)

        if len(matches) > 1:
            break
        else:
            spacer += 10

    if len(matches) == 1:
        print('test')
    else:
        print(len(matches))

    # cropped = img.crop( ( x, y, x + width , y + height ) )
    # crop_area = (x0-300, y1-200, x1+300, y0+200)

    # cropped_example = draw_image.crop(crop_area)

    # output_file_name = "d_" + str(field.objid) + ".png"
    # cropped_example.save('mturk_images/' + output_file_name, "PNG")

    # break

for pdfImage in pdfImages:
    pdfImages[pdfImage][0].show()