import argparse
import io
import logging
import pathlib
import shutil
import subprocess
import sys
import tempfile

import sqlite3

from bs4 import BeautifulSoup
import pypdf
import weasyprint

use_wkhtmltopdf = False


def determine_key(key_index: int = None, accidentals: int = None):
    if key_index < 0:
        return "C"
    key = ('C', 'D', 'E', 'F', 'G', 'A', 'B')[key_index]
    key += 'b' if accidentals < 0 else ('#' if accidentals > 0 else '')
    return key


htfc = {
    'C': 0,
    'C#': 1,
    'Db': 1,
    'D': 2,
    'D#': 3,
    'Eb': 3,
    'E': 4,
    'F': 5,
    'F#': 6,
    'Gb': 6,
    'G': 7,
    'G#': 8,
    'Ab': 8,
    'A': 9,
    'A#': 10,
    'Bb': 10,
    'B': 11
}


def determine_half_tones_from_c(key: str = None):
    return htfc[key]


def generate_path (tempdir_path, filename, suffix):
    prefix = pathlib.Path(filename).stem
    # _, rv = tempfile.mkstemp(dir=tempdir_path, suffix=suffix, prefix=prefix + '_')
    rv = f'{tempdir_path}/{prefix}{suffix}'
    return rv


def generate_path_pdf(chordpro: str = None, transpose = 0, tempdir_path = None, index: int = 0):
    html_filename = generate_path(tempdir_path, chordpro, f'_{index}.html')

    typeset_args = ['chordpro', '--generate=HTML', f'--output={html_filename}', '--diagrams=none', '--no-strict']
    if transpose is not None and transpose != 0:
        typeset_args.append(f'--transpose={transpose}')
    typeset_args.append(chordpro)
    logging.info('executing %s', typeset_args)
    typeset = subprocess.run(typeset_args)
    if typeset.returncode != 0:
        logging.error ('got rc = %d', typeset.returncode)
        return None

    fixed_html_filename = generate_path(tempdir_path, chordpro, f'_{index}_fixed.html')
    with open(html_filename) as fp:
        soup = BeautifulSoup(fp, 'html.parser')

        for tag in soup.find_all("tr", class_="chords"):
            for td in tag.find_all('td'):
                chord = td.string
                if chord.startswith('*'):
                    chord2 = chord[1:]
                    td.string = chord2

        with open(fixed_html_filename, "wb") as file:
            file.write(soup.prettify("utf-8", formatter=None))

    pdf_filename = generate_path(tempdir_path, chordpro, f'_{index}.pdf')

    weasy = weasyprint.HTML(filename=fixed_html_filename)
    weasy.write_pdf(target=pdf_filename)

    return pdf_filename


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', required=True)
    parser.add_argument('--setlist', required=True)
    args = parser.parse_args(argv)

    con = sqlite3.connect(f'{args.dir}/mobilesheets.db')
    con.row_factory = dict_factory # sqlite3.Row

    res = con.execute('''
select 
Setlists.Name,
Songs.title,
TextDisplaySettings.EnableTranpose,
TextDisplaySettings.Transpose,
TextDisplaySettings.Key,
TextDisplaySettings.TransposeKey,
TextDisplaySettings.UseSharps,
Files.Path
from Setlists
left join SetlistSong on SetlistSong.SetListId = Setlists.Id
left join Songs on Songs.Id = SetlistSong.SongId
left join TextDisplaySettings on TextDisplaySettings.SongId = SetlistSong.SongId
left join Files on Files.SongId = SetlistSong.SongId
where Setlists.name = ?
    ''',
    (args.setlist,))

    #tempdir = tempfile.mkdtemp()
    tempdir = 'test_temp'
    logging.info ("temp files go to %s", tempdir)

    shutil.copy('chordpro.css', tempdir + '/chordpro.css')
    shutil.copy('chordpro.css', tempdir + '/chordpro_print.css')

    output_pdfs = [ ]
    for i, f in enumerate(res):
        logging.info ("got %s from database", f)
        #print(type(f), f)

        p = f['Path']
        if p is None:
            continue
        if not p.endswith('.chordpro'):
            continue
        #et = f['EnableTranpose']  # they made a typo when they named it!

        # per: https://www.zubersoft.com/mobilesheets/forum/thread-14026-post-59339.html#pid59339
        #
        # UseSharps is how many accidentals the transpose key has (-1 is flat, 0 is natural, 1 is sharp).
        # Transpose is the letter from C to B where C is 0 and B is 6.
        #
        # TransposeKey is the number of accidentals for the document key.
        # Key is the letter for the document key (like TransposeKey above, from C to B).
        document_key = determine_key(f['Key'], f['TransposeKey'])
        transpose_key = determine_key(f['Transpose'], f['UseSharps'])

        document_halftones = determine_half_tones_from_c(document_key)
        transpose_halftones = determine_half_tones_from_c(transpose_key)
        transpose_amount = ((transpose_halftones - document_halftones) + 12) % 12
        logging.info ('Transposing from %s (%s) to %s (%s)', document_key, document_halftones, transpose_key, transpose_halftones)
        if transpose_key.endswith('b'):
            transpose_amount = transpose_amount - 12

        pdf_file = generate_path_pdf(chordpro=f'{args.dir}/{p}', transpose=transpose_amount, tempdir_path=tempdir, index=i)
        if pdf_file is not None:
            output_pdfs.append(pdf_file)
            #break

    logging.info('output PDFs = %s', output_pdfs)

    merger = pypdf.PdfWriter()

    blank_page_html = '''
<!DOCTYPE html>
<html lang="en"><head><style>
html, body {
    height: 100%;
    margin: 0; /* Remove default body margin */
}

.container {
    display: flex;
    justify-content: center; /* For horizontal centering */
    align-items: center; /* For vertical centering */
    height: 100%; /* Or a specific height if not full page */
}

.middle {
    /* Your div's styles */
}
</style></head><body><div class="container"><div class="middle">This page intentionally left blank.</div></div></body></html>
    '''
    blank_page_pdf = io.BytesIO()
    weasyprint.HTML(string=blank_page_html).write_pdf(blank_page_pdf)

    for pdf in output_pdfs:
        adding_reader = pypdf.PdfReader(pdf)
        adding_page_count = adding_reader.get_num_pages()
        result_page_count = merger.get_num_pages()

        adding_message = ""
        if adding_page_count % 2 == 0:
            if result_page_count % 2 == 0:
                adding_message = 'adding a blank page, then '
                merger.append(blank_page_pdf)

        logging.info ('%sadding %d pages from %s to existing %d pages',
                      adding_message, adding_page_count, pdf, result_page_count)

        merger.append(adding_reader)

    merger.write(f'{args.dir}/{args.setlist}.pdf')
    merger.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])