# coding=utf-8

import os
import time
import uuid
import zipfile

import magic
from lxml import etree

from . import userlist


version = '0.5.1'  # 2015.12.10

media_table = [
    ['image/gif', ['.gif'], 'Images'],
    ['image/jpeg', ['.jpg', 'jpeg'], 'Images'],
    ['image/png', ['.png'], 'Images'],
    ['image/svg+xml', ['.svg'], 'Images'],

    ['application/xhtml+xml', ['.xhtml'], 'Text'],

    ['application/x-dtbncx+xml', ['.ncx'], '?'],

    ['application/vnd.ms-opentype', ['.otf', '.ttf', '.ttc'], 'Fonts'],
    ['application/font-woff', ['.woff'], 'Fonts'],
    ['application/smil+xml', [], ''],
    ['application/pls+xml', [], ''],

    ['audio/mpeg', [], ''],
    ['audio/mp4', ['.mp4'], ''],

    ['text/css', ['.css'], 'Styles'],

    ['text/javascript', ['.js'], 'Scripts'],
]


class PathError(Exception):
    pass


class MediaTypeError(Exception):
    pass


class File(object):
    def __init__(self, path, binary):
        self._id = uuid.uuid1()
        self._binary = binary
        self._path = path

    @property
    def path(self):
        return self._path

    @property
    def binary(self):
        return self._binary

    def get_mime(self):
        m = None
        for mime, exts, dir_name in media_table:
            if self.extension in exts:
                m = mime
                break
        return m

    @property
    def extension(self):
        return os.path.splitext(self._path)[1]


class Epub(object):
    def __init__(self,):
        self._files_root_dir = 'EPUB'
        self._content_path = '{}/content.opf'.format(self._files_root_dir)
        self._container_path = 'META-INF/container.xml'
        # self.EPUB2fallback = False

        self.title = None
        self.identifier = uuid.uuid1().urn
        self.language = None

        self._cover = None

        # self._cover_xhtml = None  # EPUB not support xhtml to be cover yet

        self._nav_file = None

        self._sections = []
        '''
        [
            {
                'title': '1 XXX',
                'link': '',
                'sub_sections':
                    [
                        'title': '1.2 XXX', 'link': '', 'sub_sections': [...]
                    ]
            }
        ]
        '''
        def spine_add_check(item):
            if item['file'] not in self.files:
                raise ValueError('file not in files')
        self._spine = userlist.UserList(add_check_fun=spine_add_check)

        def files_add_check(item):
            if item.path in [file.path for file in self.files]:
                raise ValueError('file.path is already in files')
        self._files = userlist.UserList(add_check_fun=files_add_check)

        def landmarks_add_check(item):
            if item['type'] not in ['cover', 'titlepage', 'frontmatter', 'bodymatter', 'backmatter', 'toc', 'loi',
                                    'lot', 'preface', 'bibliography', 'index', 'glossary', 'acknowledgments']:
                raise ValueError('landmark type is wrong')
        self._landmarks = userlist.UserList(add_check_fun=landmarks_add_check)

    def set_title(self, title):
        self.title = title

    def set_identifier(self, identifier):
        self.identifier = identifier

    def set_language(self, language):
        self.language = language

    def tag_cover(self, file):  # need more code
        if file not in self.files:
            raise Exception
        if magic.from_buffer(file.binary, mime=True) not in \
                [one[0].encode() for one in media_table if one[0].startswith('image')]:
            raise MediaTypeError('Media type is not a image')
        self._cover = file

    @property
    def files(self):
        return self._files

    @property
    def spine(self):
        return self._spine

    @property
    def landmarks(self):
        return self._landmarks

    def set_toc(self, branch, link=None):
        """
        set table of contents in the book

        :param branch: an list form of chapters and sections, like: ['Chapter 1 ', 'Section 1']
        :param link: path of file in epub
        :return: None
        """
        section = self._create_and_get_section(self._sections, branch)
        section['link'] = link

    def write(self, filename):
        zip_file = zipfile.ZipFile(filename, 'w')
        zip_file.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)

        for file in self._files:
            zip_file.writestr('{}/{}'.format(self._files_root_dir, file.path), file.binary, zipfile.ZIP_DEFLATED)

        for doc, path in ((self._get_container(), self._container_path),
                          (self._get_xml_content(), self._content_path)):
            zip_file.writestr(path, self._tostring(doc), zipfile.ZIP_DEFLATED)

        zip_file.writestr('{}/{}'.format(self._files_root_dir, self._nav_file.path), self._nav_file.binary)

    @staticmethod
    def _create_and_get_section(sections, branch):
        """

        :param sections:
        :param branch:
        :return:
        """
        if len(branch) > 1:
            sub_sections = None
            for section in sections:
                if section['title'] == branch[0]:
                    sub_sections = section['sub_sections']
                    break

            if not sub_sections:
                sub_sections = []
                sections.append({'title': branch[0], 'sub_sections': sub_sections})

            return Epub._create_and_get_section(sub_sections, branch[1:])

        elif len(branch) == 1:
            s = None
            for section in sections:
                if section['title'] == branch[0]:
                    s = section

            if not s:
                s = {'title': branch[0], 'sub_sections': []}
                sections.append(s)
            return s

    @staticmethod
    def _get_file_id(file):
        return file.path.replace('/', '_')

    @staticmethod
    def _tostring(doc):
        return etree.tostring(doc, pretty_print=True, encoding='utf-8', xml_declaration=True, standalone="yes")

    def _get_container(self):
        doc = etree.Element('container', version='1.0', xmlns='urn:oasis:names:tc:opendocument:xmlns:container')
        rootfiles = etree.SubElement(doc, 'rootfiles')
        rootfile = etree.SubElement(rootfiles, 'rootfile')
        rootfile.set('full-path', self._content_path)
        rootfile.set('media-type', 'application/oebps-package+xml')
        return doc

    def _get_xml_content(self):
        doc = etree.Element('package', xmlns='http://www.idpf.org/2007/opf', version='3.0')
        doc.set('unique-identifier', 'uid')
        self._create_xml_content_metadata(doc)
        self._create_xml_content_manifest(doc)
        self._create_xml_content_spine(doc)
        self._create_xml_content_guide(doc)
        return doc

    def _create_xml_content_metadata(self, node):
        dc = "http://purl.org/dc/elements/1.1/"
        opf = "http://www.idpf.org/2007/opf"

        metadata = etree.SubElement(node, 'metadata', nsmap={'dc': dc, 'opf': opf})

        dc_identifier = etree.SubElement(metadata, '{' + dc + '}' + 'identifier')
        dc_identifier.set('id', 'uid')
        dc_identifier.text = self.identifier
        dc_title = etree.SubElement(metadata, '{' + dc + '}' + 'title')
        dc_title.text = self.title
        dc_language = etree.SubElement(metadata, '{' + dc + '}' + 'language')
        dc_language.text = self.language

        meta_property_dcterms_modified = etree.SubElement(metadata, 'meta', property='dcterms:modified')
        meta_property_dcterms_modified.text = time.strftime('%Y-%m-%dT%XZ', time.gmtime())
        '''
        <dc:language>en</dc:language>
        <meta property="dcterms:modified">2011-01-01T12:00:00Z</meta>
        '''

    def _create_xml_content_manifest(self, node):
        self._update_nav_file()
        manifest = etree.SubElement(node, 'manifest')
        item = etree.SubElement(manifest, 'item',  properties='nav', href=self._nav_file.path, id='nav')
        item.set('media-type', self._nav_file.get_mime())

        for file in self._files:
            item = etree.SubElement(manifest, 'item', href=file.path, id=self._get_file_id(file))
            item.set('media-type', file.get_mime())

            if file is self._cover:
                item.set('properties', 'cover-image')

            # Why should set properties="scripted"
            if file.get_mime() == 'application/xhtml+xml':
                page = etree.HTML(file.binary)
                for script in page.xpath('//script'):
                    if 'src' in script.attrib.keys():
                        item.set('properties', 'scripted')
                        break

    def _create_xml_content_spine(self, node):
        spine = etree.SubElement(node, 'spine')
        for joint in self.spine:
            etree.SubElement(spine, 'itemref', idref=self._get_file_id(joint['file']))

    def _create_xml_content_guide(self, node):
        pass

    def _get_nav(self):
        epub = 'http://www.idpf.org/2007/ops'
        doc = etree.Element('html', xmlns='http://www.w3.org/1999/xhtml',
                            nsmap={'epub': epub})

        etree.SubElement(doc, 'head')
        body = etree.SubElement(doc, 'body')

        nav_t = etree.SubElement(body, 'nav', id='toc')
        nav_t.set('{' + epub + '}' + 'type', 'toc')
        Epub._get_toc_ol_node(nav_t, self._sections)

        nav_l = etree.SubElement(body, 'nav', id='landmarks')
        nav_l.set('{' + epub + '}' + 'type', 'landmarks')
        self._get_landmarks_ol_node(nav_l)
        return doc

    @staticmethod
    def _get_toc_ol_node(node, sections):
        ol = etree.SubElement(node, 'ol')
        # ol.set('hidden', 'hidden')  # for test
        for section in sections:
            li = etree.SubElement(ol, 'li')
            a = etree.SubElement(li, 'a')
            if 'link' in section.keys():
                a.set('href', section['link'])
            a.text = section['title']
            if section['sub_sections']:
                Epub._get_toc_ol_node(li, section['sub_sections'])
        return ol

    def _get_landmarks_ol_node(self, node):
        epub = 'http://www.idpf.org/2007/ops'

        ol = etree.SubElement(node, 'ol')
        for landmark in self.landmarks:
            li = etree.SubElement(ol, 'li')
            a = etree.SubElement(li, 'a')
            a.set('href', landmark['file'].path)
            a.set('{' + epub + '}' + 'type', landmark['type'])
            a.text = landmark['text']

        return ol

    def _update_nav_file(self):
        binary = Epub._tostring(self._get_nav())
        if self._nav_file:
            self._nav_file._binary = binary
        else:
            self._nav_file = File('nav.xhtml', binary)


class EasyEpub(object):
    def __init__(self):
        self._epub = Epub()

        self._cover_image = None

        self._cover_page_file = None
        self._cover_joint = None
        self._cover_landmark = None

        # self._landmark_bodymatter = None ???

        self.set_language = self._epub.set_language
        self.set_title = self._epub.set_title
        self.set_identifier = self._epub.set_identifier

        self.set_toc = self._epub.set_toc
        self.write = self._epub.write

    def make_cover(self, image, expected_fullpath=None):
        self._bytes_check(image)

        if expected_fullpath:
            path = self._recommend_fullpath(expected_fullpath)
        else:
            extension = self._recommend_ext(image)
            path = self._recommend_fullpath('{}/cover{}'.format(self._recommend_directory(extension), extension))

        file = File(path, image)

        self._cover_image and self._epub.files.remove(self._cover_image)

        self._epub.files.append(file)
        self._epub.tag_cover(file)

        self._cover_image = file

        return file.path

    def add_page(self, page, expected_fullpath=None):
        self._bytes_check(page)
        self._page_check(page)

        if expected_fullpath:
            path = self._recommend_fullpath(expected_fullpath)
        else:
            path = self._recommend_fullpath(self._recommend_directory('.xhtml') + '/' + 'page.xhtml')
        file = File(path, page)

        self._epub.files.append(file)
        joint = {'file': file}
        # if linear is not None:
        #    joint.update({'linear': linear})
        self._epub.spine.append(joint)
        return file.path

    def add_other_file(self, bytes_data, expected_fullpath):
        self._bytes_check(bytes_data)
        path = self._recommend_fullpath(expected_fullpath)
        file = File(path, bytes_data)
        self._epub.files.append(file)
        return path

    @staticmethod
    def _bytes_check(data):
        if not isinstance(data, bytes):
            raise Exception

    @staticmethod
    def _page_check(data):
        if magic.from_buffer(data, mime=True) not in (b'application/xhtml+xml', b'application/xml'):
            raise Exception

    @staticmethod
    def _recommend_ext(binary):
        ext = None
        for mime, exts, dir_name in media_table:
            if magic.from_buffer(binary, mime=True) == mime.encode():
                ext = exts[0]
                break
        return ext

    @staticmethod
    def _recommend_directory(extension):
        directory = 'Unkown'
        for mime, extensions, dir_name in media_table:
            if extension in extensions:
                directory = dir_name
                break
        return directory

    def _recommend_fullpath(self, fullpath):
        path = fullpath
        directory, name = os.path.split(path)
        half_name, ext = os.path.splitext(name)

        i = 0
        while True:
            if path not in [file.path for file in self._epub.files]:
                break
            path = '{}/{}_{}{}'.format(directory, half_name, i, ext)
            i += 1

        return path
