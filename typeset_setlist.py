import argparse
import logging
import pathlib
import shutil
import subprocess
import sys
import tempfile

import sqlite3

import pypdf
import weasyprint

use_wkhtmltopdf = False


def generate_path (tempdir_path, filename, suffix):
    prefix = pathlib.Path(filename).stem
    # _, rv = tempfile.mkstemp(dir=tempdir_path, suffix=suffix, prefix=prefix + '_')
    rv = f'{tempdir_path}/{prefix}{suffix}'
    return rv


def generate_path_pdf(chordpro: str = None, transpose = 0, tempdir_path = None):
    html_filename = generate_path(tempdir_path, chordpro, '.html')
    typeset_args = ['chordpro', '--generate=HTML', f'--output={html_filename}', '--diagrams=none', '--no-strict']
    if transpose is not None and transpose != 0:
        typeset_args.append(f'--transpose={transpose}')
    typeset_args.append(chordpro)
    logging.info('executing %s', typeset_args)
    typeset = subprocess.run(typeset_args)

    if typeset.returncode != 0:
        logging.error ('got rc = %d', typeset.returncode)
        return None

    pdf_filename = generate_path(tempdir_path, chordpro, '.pdf')
    if use_wkhtmltopdf:
        pdf_args = [ 'wkhtmltopdf', '--header-center', 'foo foo foo', '--print-media-type', '--page-size', 'letter', '--enable-local-file-access', html_filename, pdf_filename]
        logging.info('executing %s', pdf_args)
        pdfize = subprocess.run(pdf_args)
        if pdfize.returncode != 0:
            logging.error ('got rc = %d', typeset.returncode)
            return None
    else:
        weasy = weasyprint.HTML(filename=html_filename)
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
    for f in res:
        #print(type(f), f)

        p = f['Path']
        if not p.endswith('.chordpro'):
            continue
        t = f['Transpose']
        #print(p, t)

        pdf_file = generate_path_pdf(chordpro=f'{args.dir}/{p}', transpose=t, tempdir_path=tempdir)
        if pdf_file is not None:
            output_pdfs.append(pdf_file)
            #break

    logging.info('output PDFs = %s', output_pdfs)

    merger = pypdf.PdfWriter()

    for pdf in output_pdfs:
        adding_reader = pypdf.PdfReader(pdf)
        adding_page_count = adding_reader.get_num_pages()
        result_page_count = merger.get_num_pages()
        logging.info ('adding %d pages from %s to existing %d pages', adding_page_count, pdf, result_page_count)
        merger.append(pdf)

    merger.write("result.pdf")
    merger.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main(sys.argv[1:])