### AI AGAINST CHAINS

## Installation

To install the project, make sure you have Python 3.8 or later version
and `pip` installed on your machine. And then run the following command lines.

### For Linux

```bash
git clone https://github.com/cacybernetic/ARCHIMED.git
cd ARCHIMED;
sudo rm -r .git;
git init;  # To create a new instance of git repository
```

And then,

1. `sudo apt install cmake python3-venv` Install *Cmake* and *Virtual env*;
2. `python3 -m venv .venv` create a virtual env into directory
named `env`;
3. `source .venv/bin/activate` activate the virtual environment named `.venv`;
4. `make install` install the requirements of this package.

### For Windows

```bash
git clone https://github.com/cacybernetic/ARCHIMED.git
```

```bash
cd ARCHIMED
```

And then, delete the hidden directory named `.git` located at the root
of the directory project.

And then,

1. Install python for windows;
2. Open your command prompt;
3. Run `python -m venv .venv` to create a virtual env into directory
named `.venv`;
4. Run `.venv\Scripts\activate` to activate the virtual environment;
5. Run `pip install torch==2.8.0 torchvision==0.23.0 --index-url "https://download.pytorch.org/whl/cpu"`
to install pytorch;
7. Run `pip install -r requirements.txt` to install the requirements
of this package or project;
8. Run `pip install -e .` install the package in dev mode in virtual
environment.

---

## Usage
Vous pouvez utiliser **ARCHIMED** de deux façons différentes : par ligne
de commande et par code.

### Extraction de données depuis une page web

1. La commande suivante permet d'extraire tous les paragraphes, tous les liens
vers les images et autres fichiers.

```sh
scripersite https://www.example.com -o outputs_dir
```

```python
from archmd.scripersite import WebScraper

scraper = WebScraper()
scraper.fetch("https://www.example.com")
```

```python
paragraphs = scraper.get_paragraphs()
```

```
This domain is for use in illustrative examples in documents. You may use this
    domain in literature without prior coordination or asking for permission.
More information...
```

La methode `scraper.get_images()` permet de recuperer les liens
vers toute les images.

2. La commande suivante permet de convertir les pages d'un document PDF
en des images.

```sh
pdf2img myfile.pdf -o outputs_dir --no-subdir
```

3. La commande suivante permet d'extraire les images des figures
depuis les pages d'un document PDF.

```sh
imgext myfile.pdf -o outputs_dir
```

4. La commande suivante permet d'extraction de texte et de caractères
depuis une image (OCR).

```sh
ocr myfile.jpg -o output.md
```

Ce programme extrait le texte sous format LaTeX. Ainsi,
cela traite les caractères.


## Features

- Extraction de données et de fichiers depuis une page web;
- Convertion de pages de document PDF en image;
- Extraction d'image de figure des pages de document PDF;
- Extraction de texte et de caractères depuis une image (OCR).

## Tests

To execute the unittest, make sure you have `pytest` package installed,
and then run the following command line:

```bash
make test 
```
or

```shell
pytest
```

---

## To contribute

Contributions are welcome! Please follow these steps:

1. Create a new branch for your feature (`git checkout -b feature/my-feature`);
2. Commit your changes (`git commit -m 'Adding a new feature'`);
3. Push toward the branch (`git push origin feature/my-feature`);
4. Create a new *Pull Request* or *Merge Request*.

## Licence

This project is licensed under the MIT License. See the file [LICENSE](LICENSE)
for more details, contact me please.

## Contact

For your question or suggestion, contact me please:

- **Name** : Narcisse K. ATTIOU
- **Email** :kotcholenarccisea@gmail.com
- **GitHub**:ATTIOU 19
