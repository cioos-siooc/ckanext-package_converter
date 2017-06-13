import ckanext

from ckanext.package_converter.model.metadata_format import MetadataFormats
from ckanext.package_converter.model.converter import BaseConverter
from ckanext.package_converter.model.record import Record, JSONRecord, XMLRecord
from ckanext.package_converter.model.scheming_converter import Datacite31SchemingConverter

from ckanext.scheming import helpers
import ckan.model as model
import ckan.plugins.toolkit as toolkit

import collections
from pylons import config
from xmltodict import unparse
import sys
import json

from logging import getLogger
log = getLogger(__name__)


FIELD_NAME = 'field_name'

#      return (super(SchemingResourceConverter, self).can_convert(record, check_version) and issubclass(type(record), JSONRecord))

class Datacite31SchemingResourceConverter(Datacite31SchemingConverter):

    def __init__(self):
        Datacite31SchemingConverter.__init__(self)
        ckan_resource_base_format = MetadataFormats().get_metadata_formats('ckan_resource')[0]
        self.input_format = ckan_resource_base_format

    def _datacite_converter_schema(self, resource_dict):
        try:
            schema_map = self._get_schema_map(self.output_format.get_format_name())
            metadata_resource_map = schema_map['metadata_resource']
            datacite_dict = collections.OrderedDict()
            # Header
            datacite_dict['resource']=collections.OrderedDict()
            datacite_dict['resource']['@xsi:schemaLocation'] = '{namespace} {schema}'.format(namespace=self.output_format.get_namespace(), 
                                                                                             schema=self.output_format.get_xsd_url())
            datacite_dict['resource']['@xmlns']='{namespace}'.format(namespace=self.output_format.get_namespace())
            datacite_dict['resource']['@xmlns:xsi']='http://www.w3.org/2001/XMLSchema-instance'
        
            # Identifier*
            datacite_identifier_tag = 'identifier'
            datacite_dict['resource'][datacite_identifier_tag] = {'#text': self._get_single_mapped_value(datacite_identifier_tag, resource_dict, metadata_resource_map), '@identifierType':'DOI'}

            # Titles*
            datacite_titles_tag = 'titles'
            datacite_title_tag = 'title'
            datacite_xml_lang_tag = 'xml:lang'
            datacite_dict['resource'][datacite_titles_tag] = { datacite_title_tag: [ ] }
            datacite_title_type_tag = 'titleType'
            ckan_titles = self._get_complex_mapped_value(datacite_titles_tag, datacite_title_tag, ['', datacite_title_type_tag, datacite_xml_lang_tag], resource_dict, metadata_resource_map)
            for ckan_title in ckan_titles:
                datacite_title = {'#text': ckan_title.get( datacite_title_tag, ''),
                                  '@' + datacite_xml_lang_tag: ckan_title.get( self._joinTags([datacite_title_tag, datacite_xml_lang_tag]) , 'en-us')}
                if ckan_title.get( self._joinTags([datacite_title_tag, datacite_title_type_tag]) ,''):
                    ckan_title_type =  ckan_title.get( self._joinTags([datacite_title_tag, datacite_title_type_tag]) , 'other')
                    datacite_title['@' + datacite_title_type_tag] =  self._valueToDataciteCV (ckan_title_type, datacite_title_type_tag)
                datacite_dict['resource'][datacite_titles_tag][datacite_title_tag] += [ datacite_title ]
        
            # Alternate Identifier (CKAN URL)
            ckan_package_url = config.get('ckan.site_url','') + toolkit.url_for(controller='package', action='read', id=resource_dict.get('package_id', ''))
            datacite_dict['resource']['alternateIdentifiers']={'alternateIdentifier':[{'#text':ckan_package_url, '@alternateIdentifierType':'URL'}]}

            # Sizes (not defined in scheming, taken from default CKAN resource)
            datacite_size_group_tag = 'sizes'
            datacite_size_tag = 'size'
            datacite_sizes = []
            if resource_dict.get('size', ''):
                datacite_sizes += [{'#text': resource.get('size', ' ') + ' bytes'}]
            if datacite_sizes:
                datacite_dict['resource'][datacite_size_group_tag] = {datacite_size_tag: datacite_sizes}

            # Formats (get from resources)
            datacite_format_group_tag = 'formats'
            datacite_format_tag = 'format'
            datacite_formats = []

            resource_format = self._get_single_mapped_value( self._joinTags([datacite_format_group_tag, datacite_format_tag]), 
                                                           resource_dict, metadata_resource_map, 
                                                           default=resource_dict.get('mimetype', resource_dict.get('mimetype_inner', '')))
            if resource_format:
                datacite_formats += [{'#text': resource_format}]
            if datacite_formats:
                datacite_dict['resource'][datacite_format_group_tag] = {datacite_format_tag: datacite_formats}

            # Version
            datacite_version_tag = 'version'
            datacite_version = self._get_single_mapped_value(datacite_version_tag, resource_dict, metadata_resource_map, '')
            if datacite_version:
                datacite_dict['resource'][datacite_version_tag] = {'#text': datacite_version }

            # Description
            datacite_descriptions_tag = 'descriptions'
            datacite_description_tag = 'description'
            datacite_description_type_tag = 'descriptionType'
            datacite_descriptions = []
            ckan_descriptions = self._get_complex_mapped_value(datacite_descriptions_tag, datacite_description_tag, [ '', datacite_xml_lang_tag, datacite_description_type_tag], resource_dict, metadata_resource_map)
            for ckan_description in ckan_descriptions:
                datacite_description = {'#text': ckan_description.get( datacite_description_tag, ''),
                                  '@' + datacite_description_type_tag: ckan_description.get( self._joinTags([datacite_description_tag, datacite_description_type_tag]) , 'Abstract'),
                                  '@' + datacite_xml_lang_tag: ckan_description.get( self._joinTags([datacite_description_tag, datacite_xml_lang_tag]) , 'en-us')}
                datacite_descriptions += [ datacite_description ]
            if datacite_descriptions:
                datacite_dict['resource'][datacite_descriptions_tag] = { datacite_description_tag: datacite_descriptions }

            # Convert to xml
            converted_package = unparse(datacite_dict, pretty=True)
        except Exception as e:
            log.debug('EXCEPTION')
            log.debug(e)
            return None
        return converted_package
