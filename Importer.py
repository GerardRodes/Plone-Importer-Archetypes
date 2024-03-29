#!/opt/Plone-4.3.6/Python-2.7/bin/python
# -*- coding: utf-8 -*-

# PARAMETERS  
#   -plonePortal:       instance of plone portal
#   -targetFolderPath:  string, path where objects will be createds
#   -xmlPath:           string, path where the xml to read is located
#   -attrName:          string, name of the tag of the item to create the object [OPTIONAL] (if items are provided they will use by default)
#   -items:             list, items to create [OPTIONAL] (if attrName is provided it will look for every item with the especified tag)
#   -structure:         list of dicts, depending of the nature of the field it can have different attributes
#   -ignoreIfExists:    boolean, if is set to true, content with existing IDs on Plone portal won't be created
#   -maxRetries:        int, number of retries for failed downloads
#
# ATTRIBUTES ON STRUCTURE
#   -contenttype: Specifies Plone ContentType
#   -title:       Title of the content, it can have replacements from the item itself that have to be specified with '{ANY_ATTRIBUTE}', example: {'title': 'Boletin {numboletin}'}
#   -id:          String to set the id of the content, if not defined title will be used instead.
#   -field:       Name of the field at Plone ContentType Schema
#   -type:        Type of the field (String, DateTime, ...)
#   -attr:        Name of the tag at the item on the XML (if not provided field will be used as default)
#   -filter:      Function where will be pass the ultimate value of the field and the item dictionary to let some transformations before setting the field
#   -format:      [DateTime Only] Specifies the format that will have the date string, example: '%Y-%m-%d'
#   -urlBuilder:  [File Only] Function to build the url where the file will be downloaded, field value and item dictionary are passed as parameters
#
#
# SUPPORTED FIELD TYPES ON STRUCTURE:
#   String, DateTime, File, Address

import urllib
import os
import xml.etree.ElementTree as ET
from Products.CMFCore.utils import getToolByName
import re
import time
from DateTime import DateTime
from datetime import date, datetime
import transaction
from Products.CMFPlone.utils import safe_unicode
import json
import urllib2
import sys
from HTMLParser import HTMLParser
from plone import api

API_KEY = "AIzaSyAopezY7RwnGO4X4xds7IV0xvBc5dp5JAg"

class Importer:

  def __init__(self, publish = True, plonePortal = None, targetFolderPath = None, xmlPath = None, attrName = None, items = None, structure = None, ignoreIfExists = False, updateIfExists = True, retryDownloads = True, maxRetries = 5):
    self.portal           = plonePortal
    self.targetFolderPath = targetFolderPath
    self.xmlPath          = xmlPath
    self.logFileName      = datetime.now().strftime('%x %X').replace('/', '-') + '.txt'
    self.logPath          = '/'.join(xmlPath.split('/')[:-1] + ['logs'])
    self.attrName         = attrName
    self.items            = items
    self.structure        = structure
    self.ignoreIfExists   = ignoreIfExists
    self.updateIfExists   = updateIfExists
    self.retryDownloads   = retryDownloads
    self.maxRetries       = 5
    self.publish          = publish
    self.log              = {
                              'stats':{
                                'total': 0,
                                'success': 0,
                                'ignored': 0,
                                'failed': 0,
                                'exists': 0,
                                'updated': 0,
                                'fileDownloadsSuccess': 0,
                                'fileDownloadsError': 0,
                              },
                              'events': [],
                              'failedDownloads': []
                            }

    if not os.path.exists(self.logPath):
      os.makedirs(self.logPath)

    for field in self.structure:
      if not field.get('attr', None) and field.get('field', None):
        field['attr'] = field['field']

    if plonePortal is not None and targetFolderPath is not None:
      self.setFolder()

    if xmlPath is not None:
      self.setXml()

    if attrName is not None and self.items is None:
      self.findAllItems()

    if structure is not None and self.items is not None:
      self.buildObjects()



  #
  # CONFIGURATION METHODS
  #

  ##parses xml as json at .json and as tree at .tree
  def setXml(self, xmlPath = None):
    xml = xmlPath if xmlPath is not None else self.xmlPath
    self.addEvent('Reading xml...')

    try:
      with open(xml, "r+") as f:
        xmlstring = f.read()
        f.seek(0)
        f.write(xmlstring.replace('(NULL)', ''))
        f.truncate()
    except:
      pass

    self.tree = ET.parse(xml)
    self.addEvent('xml loaded')
    self.addEvent('Parsing xml...')
    self.json = self.parseXml(self.tree.getroot())
    self.addEvent('xml parsed to json')


  @staticmethod
  def createPath(path, current_folder):
    # Folder doesn't exists, creating
    splitted_path = path if isinstance(path, list) else path.split('/')
    splitted_path = [folder for folder in splitted_path if folder]
    i = 2   # 2 because /fs-database/plonesite/
    while i < len(splitted_path):
      if splitted_path[i] not in current_folder.keys():
        title = ' '.join(splitted_path[i].capitalize().split('-'))
        current_folder.invokeFactory('Folder', splitted_path[i])
        new_folder = getattr(current_folder, splitted_path[i])
        new_folder.setTitle(title)
        new_folder.reindexObject()
        transaction.commit()

        print 'Created folder: ' + title
        current_folder = new_folder
      else:
        current_folder = getattr(current_folder, splitted_path[i])

      i += 1

    return current_folder


  def setFolder(self, folderPath = None):
    path = self.targetFolderPath if folderPath is None else folderPath

    try:
      self.targetFolder = self.portal.restrictedTraverse(path)
    except Exception as e:
      self.targetFolder = self.createPath(path, self.portal)

    return self.targetFolder



  #
  # INTERNAL METHODS
  #

  ##Parses XML to JSON
  def parseXml(self, treeElement, isRoot = True):
    element = {}
    
    if treeElement.text:
      text = treeElement.text.strip()
      if text  != '':
        element['text'] = text
    
    for attr in treeElement.attrib:
      element['@'+attr] = treeElement.attrib[attr]
    
    childDone = []
    for children in treeElement:
      if children.tag not in childDone:
        childDone.append(children.tag)
        siblings = treeElement.findall(children.tag)
        
        if len(siblings) > 1:
          element[children.tag] = []
          for i, sibling in enumerate(siblings):
            element[children.tag].append({})
            element[children.tag][i] = self.parseXml(sibling, isRoot=False)
        else:
          element[children.tag] = self.parseXml(children, isRoot=False)

    if isRoot:
      return {treeElement.tag: element}
    else:
      return element


  def findAllItems(self, json = None, ParamAttrName = None):
    attrName = ParamAttrName if ParamAttrName is not None else self.attrName
    self.items = []
    for item in self.tree.getroot().findall(attrName):
      self.items.append(self.parseXml(item, isRoot = False))


  def buildObjects(self):

    plone_utils = getToolByName(self.portal, 'plone_utils', None)
    workflowTool = getToolByName(self.portal, 'portal_workflow')
    targetFolder = self.portal.restrictedTraverse(self.targetFolderPath)
    self.log['stats']['total'] = len(self.items)

    for i, item in enumerate(self.items):
      self.addEvent('--- ITEM '+str(i+1)+'/'+str(self.log['stats']['total'])+' START ---')
      newId = ''
      try:
        newObject = None

        newTitle = {'structure': filter(lambda info: info.get('title', None), self.structure)[0]['title']}
        newTitle['string'] = newTitle['structure']

        if newTitle['structure']:
          titleParts = re.compile('(?<=\{)(.*?)(?=\})').split(newTitle['structure'])
          titleParts = filter(lambda part: '{' not in part and '}' not in part, titleParts)

          for part in titleParts:
            try:
              attrName = filter(lambda field: field.get('field', None) == part, self.structure)[0]['attr']
            except:
              attrName = part
            newTitle['string'] = newTitle['string'].replace('{'+part+'}',item[attrName]['text'])
        try:
          self.addEvent('Building object: '+str(newTitle['string']))
        except:
          pass


        idStructure = {'structure': filter(lambda info: info.get('id', None), self.structure)}
        
        if idStructure['structure']:
          idStructure['string'] = idStructure['structure'][0]['id']
          idParts = re.compile('(?<=\{)(.*?)(?=\})').split(idStructure['structure'][0]['id'])
          idParts = filter(lambda part: '{' not in part and '}' not in part, idParts)
          for part in idParts:
            try:
              attrName = filter(lambda field: field.get('field', None) == part, self.structure)[0]['attr']
            except:
              attrName = part
            idStructure['string'] = idStructure['string'].replace('{'+part+'}',item[attrName]['text'])

          newId = plone_utils.normalizeString(safe_unicode(idStructure['string']))
        else:
          newId = plone_utils.normalizeString(safe_unicode(newTitle['string']))

        newObject = None
        if getattr(targetFolder, newId, None):
          if self.updateIfExists:
            self.log['stats']['updated'] += 1
            self.addEvent(newId+' already exists, updating')
            newObject = getattr(targetFolder, str(newId))
          elif not self.ignoreIfExists:
            newId += '-'+str(int(round(time.time() * 1000)))
            self.log['stats']['exists'] += 1
          else:
            self.log['stats']['ignored'] += 1
            self.addEvent(newId+' already exists, ignoring')
            continue
        self.addEvent('Generated id: '+newId)

        if not newObject:
          contenttype = filter(lambda info: info.get('contenttype', None), self.structure)[0]['contenttype']
          targetFolder.invokeFactory(contenttype, str(newId))
          newObject = getattr(targetFolder, str(newId))
          self.addEvent('ContentType: '+contenttype)

        newObject.setTitle(newTitle['string'])

        fields = filter(lambda info: info.get('field', None), self.structure)

        ##############
        # Decides if publish or not the content
        ##############
        publish_definition = [info for info in self.structure if info.get('publish_if', None)]

        for field in fields:
          fieldValue = None
          value = ''
          if field['attr'] in item:
            value = item[field['attr']].get('text', None)

          if value != None:
            setter = getattr(newObject, 'set' + field['field'][0].capitalize() + field['field'][1:])

            if field['type'] == 'String':
              fieldValue = value

            elif field['type'] == 'Boolean':
              fieldValue = value

            elif field['type'] == 'DateTime':
              fieldValue = DateTime(datetime.strptime(value,field['format']))

            elif field['type'] == 'File':
              try:
                self.addEvent('Trying to download file: ' + str(value))
                self.downloadFile(field, value, item, newObject)
              except:
                self.addEvent('Error downloading file.')
                pass

            elif field['type'] == 'Address':
              fieldValue = self.getCoordinates(value)
              fieldValue = str(fieldValue['lat']) + '|' + str(fieldValue['lng'])
            else:
              fieldValue = value


            if field['type'] != 'File':
              filterFunc = field.get('filter', None)
              if filterFunc:
                self.addEvent('Applying filter '+str(filterFunc))
                fieldValue = filterFunc(fieldValue, item)

              setter(fieldValue)
            
            self.addEvent('Populated '+field['type']+' field '+field['field'])
          else:
            self.addEvent('Field ' + field['field'] + ' empty value')


        if publish_definition:
          self.publish = publish_definition[0]['publish_if'](item, newObject)

        if self.publish:
          try:
            self.addEvent('Trying to publish object...')
            workflowTool.doActionFor(newObject, 'publish', comment="published programmatically")
            self.addEvent('Success')
          except Exception as e:
            self.addEvent('Failed: ' + str(e))
        try:
          newObject.reindexObject()
        except:
          pass
        self.log['stats']['success'] += 1

      except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(exc_type, fname, exc_tb.tb_lineno)
        self.addEvent('ERROR: ' + str(e) + ' \n line:' + str(exc_tb.tb_lineno))
        if getattr(targetFolder, newId, None):
          self.addEvent('type value: '+str(type(fieldValue)))
          self.addEvent('field value: '+str(fieldValue))
          self.addEvent('DELETING OBJECT: '+str(newId))
          targetFolder.manage_delObjects([newId])

        self.log['stats']['failed'] += 1


      if i % 50 == 0:
        self.addEvent('transaction savepoint')
        transaction.savepoint(True)

      self.addEvent('--- ITEM '+str(i+1)+'/'+str(self.log['stats']['total'])+' END ---')

    self.addEvent('commit')
    transaction.commit()

    if self.log['stats']['fileDownloadsError'] > 0:
      for attempt in range(self.maxRetries):
        self.addEvent('Retrying failed downloads ('+str(self.log['stats']['fileDownloadsError'])+'), attempt '+str(attempt+1)+'/'+str(self.maxRetries))
        self.log['stats']['fileDownloadsError'] = 0
        queue = self.log['failedDownloads']
        self.log['failedDownloads'] = []
        for fD in queue:
          self.downloadFile(fD['field'], fD['value'], fD['item'], fD['object'])

    if len(self.log['failedDownloads']) > 0:
      self.log['failedDownloads'] = map(lambda fD: {'id':fD['object'].getId() ,'url':fD['field']['urlBuilder'](fD['value'], fD['item'])}, self.log['failedDownloads'])


  def addEvent(self, event):
    print event
    with open(self.logPath + '/' + self.logFileName, 'a+') as f:
      f.write(str(datetime.now()) + ' -- ' + event + '\n')


  def downloadFile(self, field, value, item, newObject):
    url = field['urlBuilder'](value, item)
    self.addEvent('Downloading file '+value+' from '+str(url))
    try:
      file = urllib.urlopen(url)
      if file.getcode() == 404:
        raise Exception(file.getcode())

      self.addEvent('Reading file...')
      fileData = file.read()
      file.close()
      self.addEvent('File readed, size: '+str(len(fileData)))
      setter = getattr(newObject, 'set' + field['field'][0].capitalize() + field['field'][1:])
      setter(fileData, filename=value.encode("utf-8"))
      self.log['stats']['fileDownloadsSuccess'] += 1
    except Exception as e:
      self.log['stats']['fileDownloadsError'] += 1
      self.log['failedDownloads'].append({'field': field, 'value': value, 'item': item, 'object': newObject})
      self.addEvent('ERROR: download failed from: '+url+' - '+str(e))


  def getCoordinates(self, address):
    url = "https://maps.googleapis.com/maps/api/geocode/json?address=" + urllib.quote_plus(address.encode('utf-8')) + "&key=" + API_KEY
    resp = json.load(urllib2.urlopen(url))

    try:
      return resp['results'][0]['geometry']['location']
    except:
      return {
        "lat" : 0,
        "lng" : 0
      }
