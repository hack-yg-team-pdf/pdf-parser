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
import json
import glob

from pyqtree import Index

from pdfminer.layout import LAParams, LTTextBox,LTChar, LTFigure

def parse_obj(lt_objs, quadtree_index):
    # loop over the object list
    for obj in lt_objs:
        # if it's a textbox, print text and location
        if isinstance(obj, pdfminer.layout.LTTextBoxHorizontal):
            field_texts = obj.get_text().split('\n')
            if len(field_texts) == 1:
                literal_text = obj.get_text().replace('_', '').strip()
                quadtree_index.insert((literal_text, obj.bbox), obj.bbox)
                print("%6d, %6d, %s" % (obj.bbox[0], obj.bbox[1], literal_text))
            else:
                i = 0
                spacing = (obj.bbox[3] - obj.bbox[1]) / len(field_texts)
                for field_text in field_texts:
                    literal_text = field_text.replace('_', '').strip()
                    new_bbox = [obj.bbox[0], obj.bbox[1] + i*spacing, obj.bbox[2], obj.bbox[1] + spacing]
                    i += 1
                    if len(literal_text.strip()) > 0:
                        quadtree_index.insert((literal_text, new_bbox), new_bbox)
                        print("%6d, %6d, %s" % (new_bbox[0], new_bbox[1], literal_text))

files = glob.glob('original_pdfs/*.pdf')

for filename in files:
    code = filename.split('/')[1].split('.')[0]
    json_name = 'output_json/' + code + '.json'
    print(json_name)

    fp = open(filename, 'rb')

    images = convert_from_path(filename)

    parser = PDFParser(fp)
    doc = PDFDocument(parser, password='')

    #if not doc.is_extractable:
    #    raise PDFTextExtractionNotAllowed

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

    pdfImages = {}
    for i, pdfPage in enumerate(PDFPage.create_pages(doc)):
        quadtree_index = Index(bbox=(0, 0, pdfPage.mediabox[2], pdfPage.mediabox[3]))
        pdfImages[pdfPage.pageid] = (images[i], images[i].copy(), quadtree_index)

        # read the page into a layout object
        interpreter.process_page(pdfPage)
        layout = device.get_result()

        # extract text from this object
        parse_obj(layout._objs, quadtree_index)

    sanitized_fields = []

    if 'AcroForm' not in doc.catalog:
        continue

    fields = resolve1(doc.catalog['AcroForm'])['Fields']
    if type(fields) is not list:
        continue

    for field in fields:
        resolved_field = resolve1(field)
        name, value, rect, page_id = resolved_field.get('T'), resolved_field.get('V'), resolved_field.get('Rect'), resolved_field.get('P')
        # PDF Rect comes in format

        is_textfield = True
        if 'FT' not in resolved_field:
            is_textfield = True
        elif resolved_field['FT'].name == 'Tx':
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

        # print('{0}: {1}, {2}'.format(name, value, rect))

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
            if spacer > 500:
                break
            # keep increasing area until we grab at least one textfield
            if is_textfield:
                quadrect = [rect[0] - spacer, rect[1] - spacer, rect[2], rect[3]]
            else:
                quadrect = [rect[0], rect[1], rect[2]+ spacer, rect[3] + spacer]

            matches = quadtree_index.intersect(quadrect)

            if len(matches) > 1:
                break
            else:
                spacer += 5

        # handle unfound case
        if len(matches) == 0:
            break

        # if len(matches) == 1:
        #     print('test')
        #else:
        #     print(len(matches))

        field_id = field.objid
        match = matches[0]
        field_description = match[0]
        quadtree_index.remove(match, match[1])

        if is_textfield:
            field_type = 'string'
        else:
            field_type = 'boolean'

        sanitized_fields.append((field_id, field_type, field_description))

        # cropped = img.crop( ( x, y, x + width , y + height ) )
        # crop_area = (x0-300, y1-200, x1+300, y0+200)

        # cropped_example = draw_image.crop(crop_area)

        # output_file_name = "d_" + str(field.objid) + ".png"
        # cropped_example.save('mturk_images/' + output_file_name, "PNG")

        # break

    data = {}
    data['fields'] = 'value'
    json_data = json.dumps(data)

    #for pdfImage in pdfImages:
    #    pdfImages[pdfImage][0].show()


    field_properties = {}
    for field in sanitized_fields:
        field_properties[field[0]] = {'type': field[1], 'description': field[2]}

    fields = {}
    fields['properties'] = field_properties
    fields['type'] = 'object'
    data['fields'] = fields

    json_data = json.dumps(data, indent=2, sort_keys=True)
    with open(json_name, 'w') as f:
        f.write(json_data)

    print(json_data)