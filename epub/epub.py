import zipfile
import random
import os
import string


from hooky import List, Dict

import xl

from .tools import identify_mime

from .package_descriptor import package_descriptor


from .metadata import Metadata


CONTAINER_PATH = 'META-INF' + os.sep + 'container.xml'

ROOT_OF_OPF = 'EPUB'


media_table = [

    # Image Types
    ['image/gif', ['.gif'], 'Images'],
    ['image/jpeg', ['.jpg', 'jpeg'], 'Images'],
    ['image/png', ['.png'], 'Images'],
    ['image/svg+xml', ['.svg'], 'Images'],

    # Application Types
    ['application/xhtml+xml', ['.html', '.xhtml'], 'Text'],
    ['application/font-sfnt', ['.otf', '.ttf', '.ttc'], 'Fonts'],  # old 'application/vnd.ms-opentype'
    ['application/font-woff', ['.woff'], 'Fonts'],
    ['application/smil+xml', [], 'Text'],  # EPUB Media Overlay documents
    ['application/pls+xml', [], ''],  # Text-to-Speech (TTS) Pronunciation lexicons

    # Audio Types
    ['audio/mpeg', [], ''],
    ['audio/mp4', ['.mp4'], ''],

    # Text Types
    ['text/html', [], 'Text'],
    ['text/css', ['.css'], 'Styles'],
    ['text/javascript', ['.js'], 'Scripts'],

    # Font Types
    ['font/woff2', ['.woff2'], 'Fonts'],
]


class Section:
    def __init__(self, title, href=None):
        self._title = title
        self._href = href
        self._subsections = []

        self._hidden_sub = None

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = value

    @property
    def href(self):
        return self._href

    @href.setter
    def href(self, value):
        self._href = value

    @property
    def subsections(self):
        return self._subsections

    @property
    def hidden_sub(self):
        return self._hidden_sub

    @hidden_sub.setter
    def hidden_sub(self, value):
        if value not in (True, False):
            raise ValueError
        else:
            self._hidden_sub = value

    def to_element(self):
        li = xl.Element('li')

        if self.href:
            a_or_span = xl.Element((None, 'a'))
            a_or_span.attributes[(None, 'href')] = self.href
        else:
            a_or_span = xl.Element((None, 'span'))

        if self.subsections:
            ol = xl.Element('ol')
            for one in self.subsections:
                ol.children.append(one.to_element())

            a_or_span.children.append(ol)

        li.children.append(a_or_span)

        return li


class Files(Dict):
    def to_element(self):
        manifest = xl.Element((None, 'manifest'))
        for path, file in self:
            item = xl.Element((None, 'item'), attributes={(None, 'href'): path, (None, 'media-type'): file.mime})
            if file.identification is not None:
                item.attributes[(None, 'id')] = file.identification

            manifest.children.append(item)

        return manifest


class File:
    def __init__(self, binary, mime=None, identification=None):
        self._binary = binary
        self.mime = mime or identify_mime(self.binary)
        self.identification = identification

    @property
    def binary(self):
        return self._binary


#####################################
# for Manifest
class Item:
    def __init__(self, href, media_type=None, id_=None):
        self._href = href
        self.media_type = media_type or identify_mime(href)
        self.id = id_

    @property
    def href(self):
        return self._href

    def to_element(self):
        e = xl.Element((None, 'item'), attributes={(None, 'href'): self.href})
        e.attributes[(None, 'media-type')] = self.media_type
        if self.id is not None:
            e.attributes[(None, 'id')] = self.id

        return e

#####################################


#####################################
# for Spine

class Spine(List):
    pass


class Itemref:
    def __init__(self, idref, linear=None):
        self._idref = idref
        self._linear = linear

    @property
    def idref(self):
        return self._idref

    def to_element(self):
        e = xl.Element((None, 'itemref'), attributes={(None, 'idref'): self.idref})

        if self._linear is True:
            e.attributes[(None, 'linear')] = 'yes'
        elif self._linear is False:
            e.attributes[(None, 'linear')] = 'no'

        return e

#####################################


class Epub:
    def __init__(self):

        self._files = Files()

        self._metadata = Metadata()

        self._manifest = List()

        self._spine = Spine()

        # nav
        self._toc = List()
        self._landmark = List()
        self._pagelist = List()

        # self._package_element.descriptor = package_descriptor

    @property
    def files(self):
        return self._files

    @property
    def metadata(self):
        return self._metadata

    @property
    def manifest(self):
        return self._manifest

    @property
    def spine(self):
        return self._spine

    @property
    def toc(self):
        return self._toc

    @property
    def landmark(self):
        return self._landmark

    @property
    def pagelist(self):
        return self._pagelist

    def _xmlstr_nav(self):
        default_ns = 'http://www.w3.org/1999/xhtml'
        epub_ns = 'http://www.idpf.org/2007/ops'

        html = xl.Element((None, 'html'), prefixes={default_ns: None, epub_ns: 'epub'})
        body = xl.Element((None, 'body'))

        if self.toc:
            nav = xl.Element((None, 'nav'), prefixes={epub_ns: 'epub'}, attributes={(epub_ns, 'type'): 'toc'})
            ol = xl.Element((None, 'ol'))

            for section in self.toc:
                ol.children.append(section.to_element())

            nav.children.append(ol)
            body.children.append(nav)

        html.children.append(body)

        return html.xml_string()

    def _xmlstr_opf(self):
        def_ns = 'http://www.idpf.org/2007/opf'
        dc_ns = 'http://purl.org/metadata/elements/1.1/'
        dcterms_ns = 'http://purl.org/metadata/terms/'
        package = xl.Element((None, 'package'),
                             prefixes={def_ns: None, dc_ns: 'metadata', dcterms_ns: 'dcterms'},
                             attributes={(None, 'version'): '3.0', (xl.URI_XML, 'lang'): 'en'})
        # metadata

        # manifest
        manifest = xl.Element((None, 'manifest'))
        for item in self.manifest:
            manifest.children.append(item.to_element())

        package.children.append(manifest)

        # spine
        spine = xl.Element((None, 'spine'))
        for itemref in self.spine:
            spine.children.append(itemref.to_element())

        package.children.append(spine)

        return package.xml_string()

    @staticmethod
    def _xmlstr_container(opf_path):
        e = xl.Element((None, 'container'))
        e.attributes[(None, 'version')] = '1.0'

        e.prefixes[None] = 'urn:oasis:names:tc:opendocument:xmlns:container'

        rootfiles = xl.Element('rootfiles')
        e.children.append(rootfiles)

        rootfile = xl.Element('rootfile')
        rootfiles.children.append(rootfile)

        rootfile.attributes['full-path'] = opf_path

        rootfile.attributes['media-type'] = 'application/oebps-package+xml'

        return xl.xml_header() + e.xml_string()

    def write(self, filename):
        z = zipfile.ZipFile(filename, 'w')
        z.writestr('mimetype', b'application/epub+zip', compress_type=zipfile.ZIP_STORED)

        for file, data in self._files:
            z.writestr(ROOT_OF_OPF + os.sep + file, data, zipfile.ZIP_DEFLATED)

        opf_path = ROOT_OF_OPF + os.sep + 'package.opf'

        while opf_path in [ROOT_OF_OPF + os.sep + path for path in self.files.keys()]:
            opf_path = ROOT_OF_OPF + os.sep + 'package_{}.opf'.format(
                random.random(''.join(random.sample(string.ascii_letters + string.digits, 8)))
            )

        z.writestr(opf_path, self._xmlstr_opf(), zipfile.ZIP_DEFLATED)

        z.writestr(CONTAINER_PATH, self._xmlstr_container(opf_path).decode(), zipfile.ZIP_DEFLATED)

        z.close()
