from pyqtree import Index
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from PIL import ImageDraw
from pdf2image import convert_from_path
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdftypes import resolve1
import csv, os, glob, json, pdfminer

def inject_text_to_quadtree(lt_objs, quadtree):
    # loop over the object list
    for obj in lt_objs:
        # if it's a textbox, inject text into quadtree with bounding box index
        if isinstance(obj, pdfminer.layout.LTTextBoxHorizontal):
            field_texts = obj.get_text().split('\n')
            if len(field_texts) == 1:
                literal_text = obj.get_text().replace('_', '').strip()
                quadtree.insert((literal_text, obj.bbox), obj.bbox)
                #print("%6d, %6d, %s" % (obj.bbox[0], obj.bbox[1], literal_text))
            else:
                # if there's breaklines in the text, separate them into individual lines for better matching
                # as a lot of the PDF make heavy use of multi-line text which screws up the label finder
                i = 0
                spacing = (obj.bbox[3] - obj.bbox[1]) / len(field_texts)
                for field_text in field_texts:
                    literal_text = field_text.replace('_', '').strip()
                    new_bbox = [obj.bbox[0], obj.bbox[1] + i*spacing, obj.bbox[2], obj.bbox[1] + spacing]
                    i += 1
                    if len(literal_text.strip()) > 0:
                        quadtree.insert((literal_text, new_bbox), new_bbox)
                        #print("%6d, %6d, %s" % (new_bbox[0], new_bbox[1], literal_text))


# returns a hash of all the pages keyed by page_id having a tuple contents of the PNG representing the PDF page and the
# pages quadtree
def prepare_pdf_pages(doc, page_images):
    pdf_processed_pages = {}

    # prep the PDF interpreter to grab the text fields
    laparams = LAParams()
    rsrcmgr = PDFResourceManager()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    for i, pdfPage in enumerate(PDFPage.create_pages(doc)):
        quadtree_index = Index(bbox=(0, 0, pdfPage.mediabox[2], pdfPage.mediabox[3]))
        pdf_processed_pages[pdfPage.pageid] = (page_images[i], quadtree_index)

        # read the page into a layout object
        interpreter.process_page(pdfPage)
        layout = device.get_result()

        # extract text from this object
        inject_text_to_quadtree(layout._objs, quadtree_index)
    return pdf_processed_pages


# returns a tuple of a lot of things; field_id, field_type, field_description, cropped_file_name, match_str
def process_form_field(field, output_file_code, pdf_processed_pages, make_crops):
    resolved_field = resolve1(field)

    # gets the details of the form field from the PDF File
    name, value, rect, page_id = resolved_field.get('T'), resolved_field.get('V'), resolved_field.get(
        'Rect'), resolved_field.get('P')

    field_id = str(field.objid)

    if 'FT' not in resolved_field:
        is_textfield = True
    elif resolved_field['FT'].name == 'Tx':
        is_textfield = True
    elif resolved_field['FT'].name == 'Btn':
        is_textfield = False
    else:
        is_textfield = True  # weird form type; assume its a text field

    if page_id is None:
        return

    page_resolved = resolve1(page_id)

    quadtree_index = pdf_processed_pages[page_id.objid][1]

    if make_crops:
        cropped_file_name = 'mturk_images/' + output_file_code + "_" + str(field_id) + ".png"
        if not os.path.isfile(cropped_file_name):
            draw_image = pdf_processed_pages[page_id.objid][
                0].copy()  # makes a copy since we want to make a fresh crop for each one

            image_height = draw_image.height

            page_width = page_resolved['MediaBox'][2]
            page_height = page_resolved['MediaBox'][3]

            scale = image_height / page_height

            x0 = rect[0] * scale
            y0 = image_height - rect[1] * scale
            x1 = rect[2] * scale
            y1 = image_height - rect[3] * scale

            draw = ImageDraw.Draw(draw_image, 'RGBA')
            draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 250, 100))

            crop_area = (0, y1 - 200, page_width * scale, y0 + 200)
            cropped_example = draw_image.crop(crop_area)

            cropped_example.save(cropped_file_name, "PNG")

    spacer = 0
    while True:
        # keep increasing area until we grab at least one textfield or get unreasonably big
        if spacer > 20:
            break
        if is_textfield:
            # textfields have their labels to the left or up
            quadrect = [rect[0] - spacer, rect[1] - spacer, rect[2], rect[3]]
        else:
            # checkboxes have their labels to the right
            quadrect = [rect[0], rect[1], rect[2] + spacer, rect[3] + spacer]

        matches = quadtree_index.intersect(quadrect)

        if len(matches) > 1:
            break
        else:
            spacer += 5

    # handle unfound case
    if len(matches) == 0:
        return

    match = matches[0]
    field_description = match[0]
    quadtree_index.remove(match, match[1])

    if is_textfield:
        field_type = 'string'
    else:
        field_type = 'boolean'

    match_text = list(map(lambda x: x[0], matches))
    match_str = ' '.join(match_text)

    return field_id, field_type, field_description, cropped_file_name, match_str


def create_json_file(filename_code, sanitized_fields):
    json_name = 'output_json/' + filename_code + '.json'

    field_properties = {}
    for field in sanitized_fields:
        field_properties[field[0]] = {'type': field[1], 'description': field[2]}

    data = {}
    fields = {}
    fields['properties'] = field_properties
    fields['type'] = 'object'
    data['fields'] = fields

    json_data = json.dumps(data, indent=2, sort_keys=True)
    with open(json_name, 'w') as f:
        f.write(json_data)


def process_pdf_file(filename, csvwriter, make_crops):
    fp = open(filename, 'rb')
    output_file_code = filename.split('/')[1].split('.')[0]

    pdf2png_images = convert_from_path(filename)

    parser = PDFParser(fp)
    doc = PDFDocument(parser, password='')  # pretty much all YG docs are encrypted with an empty password

    pdf_processed_pages = prepare_pdf_pages(doc, pdf2png_images)

    sanitized_fields = []

    if 'AcroForm' not in doc.catalog:
        return

    fields = resolve1(doc.catalog['AcroForm'])['Fields']
    if type(fields) is not list:
        return

    for field in fields:
        processed_field = process_form_field(field, output_file_code, pdf_processed_pages, make_crops)

        if processed_field is not None:
            # need to handle None return type on a fail
            (field_id, field_type, field_description, cropped_file_name, match_str) = processed_field

            if make_crops:
                csvwriter.writerow((cropped_file_name, match_str))
            sanitized_fields.append((field_id, field_type, field_description))

    create_json_file(output_file_code, sanitized_fields)


if __name__ == "__main__":
    files = glob.glob('raw_pdfs/*.pdf')

    # makes a csv file contianing references to all the images to be used for mechanical turk with surrounding text blobs
    with open('mturk.csv', mode='w') as mturk_file:
        mturk_writer = csv.writer(mturk_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        i = 0
        for filename in files:
            print('Processing (',i, ')', filename)
            i += 1
            try:
                process_pdf_file(filename, mturk_writer, True)
            except:
                print("Error processing", filename)

