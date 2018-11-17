Repo for "Team PDF" participation in [HackYG 2018](https://yukonstruct.com/hackyg/)

## PDF to JSON Parser

The Purpose of this repo is to take a collection of PDF forms from the Yukon Government and attempt to output a series of JSON files in the [JSON Forms](https://jsonforms.io/) format to make a series of web-accessible forms.

### Requirements

* Python 3.6
* Python Image Library
* PdfMiner.six (The Python 3 fork of PDFMiner)
* pdf2image


## Inputs

The Script will load all PDF files loaded into the `raw_pdfs/` directory.

## Outputs

* `mturk_images/*` - Cropped images of a specific form field for uploading to mechanical turk for field identification, filenames formatted as `{pdfid}_{form_object_id}.png`
* `mturk.csv` - Manifest of all the Mechanical turk images along with text nearby to make copy/paste easier
* `output_json/*` - Json representation of corresponding PDF form fields with a "best guess" as to field labels for JSON forms format. filenames formatted as `{pdfid}.json`
