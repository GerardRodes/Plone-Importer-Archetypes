# Plone-Importer
Automating XML imports to Plone Objects Schemata

##PARAMETERS  
- plonePortal:       instance of plone portal  
- targetFolderPath:  string, path where objects will be createds  
- xmlPath:           string, path where the xml to read is located  
- attrName:          string, name of the tag of the item to create the object [OPTIONAL] (if items are provided they will use by default)  
- items:             list, items to create [OPTIONAL] (if attrName is provided it will look for every item with the especified tag)  
- structure:         list of dicts, depending of the nature of the field it can have different attributes  
- ignoreIfExists:    boolean, if is set to true, content with existing IDs on Plone portal won't be created  
- maxRetries:        int, number of retries for failed downloads  

##ATTRIBUTES ON STRUCTURE
- contenttype: Specifies Plone ContentType  
- title:       Title of the content, it can have replacements from the item itself that have to be specified with '{ANY_ATTRIBUTE}', example: {'title': 'Boletin {numboletin}'}  
- field:       Name of the field at Plone ContentType Schema  
- type:        Type of the field (String, DateTime, ...)  
- attr:        Name of the tag at the item on the XML (if not provided field will be used as default)  
- filter:      Function where will be pass the ultimate value of the field and the item dictionary to let some transformations before setting the field  
- format:      [DateTime Only] Specifies the format that will have the date string, example: '%Y-%m-%d'  
- urlBuilder:  [File Only] Function to build the url where the file will be downloaded, field value and item dictionary are passed as parameters  

##SUPPORTED FIELD TYPES ON STRUCTURE:
- String  
- DateTime  
- File
