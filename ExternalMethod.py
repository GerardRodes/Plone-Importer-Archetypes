import json
from Importer import Importer

def importContent(self):

  contentStructure = [
    {'contenttype': 'MyContentType'},
    {'title': 'Content {numcontent}'},
    {'field': 'legislatura',  'type': 'String'},
    {'field': 'seriecontent', 'type': 'String',   'attr': 'serie_content'},
    {'field': 'aniocontent',  'type': 'String',   'attr': 'fecha_content',  'filter': lambda fecha, item: fecha[:4]},
    {'field': 'fechacontent', 'type': 'DateTime', 'attr': 'fecha_content', 'format': '%Y-%m-%d'},
    {'field': 'file',         'type': 'File',     'attr': 'content',  'urlBuilder': lambda fileName, item: 'http://www.someurl.org/files/'+item['id']['text']+'/'+fileName }
  ]

  importer = Importer(plonePortal       = self,
                      targetFolderPath  = '/folder/content',
                      xmlPath           = '/folder/lorem.xml',
                      attrName          = 'ROW',
                      structure         = contentStructure)

  print json.dumps(importer.log, indent=2, sort_keys=True)
