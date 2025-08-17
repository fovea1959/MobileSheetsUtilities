import weasyprint
def main():
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
    weasyprint.HTML(string=blank_page_html).write_pdf('test.pdf')

if __name__ == '__main__':
    main()