from bs4 import BeautifulSoup

with open("test_temp/You Didn't Have to Be So Nice.html") as fp:
    soup = BeautifulSoup(fp)

    for tag in soup.find_all("tr", class_="chords"):
        print(tag.name, tag.attrs, tag.contents)
        for td in tag.find_all('td'):
            print(' ', td.string)

            chord = td.string
            if chord.startswith('*'):
                chord2 = chord[1:]
                print(' ', chord, '->', chord2)
                td.string = chord2

    print(soup.prettify())
