from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search

from datawinners.search.query import ElasticUtilsHelper
from mangrove.form_model.project import get_entity_type_fields


REPORTER_DOC_TYPE = 'reporter'

def _add_pagination_criteria(search_parameters, search):
    start_result_number = search_parameters.get("start_result_number")
    number_of_results = search_parameters.get("number_of_results")
    return search.extra(from_=start_result_number, size=number_of_results)


def _add_response_fields(search_parameters, search):
    if 'response_fields' in search_parameters:
        search = search.fields(search_parameters['response_fields'])
    return search


def _add_sort_criteria(search_parameters, search):
    if 'sort_field' not in search_parameters:
        return search

    order_by_field = "%s_value" % search_parameters["sort_field"]
    order = search_parameters.get("order")
    order_by_criteria = "-" + order_by_field if order == '-' else order_by_field
    return search.sort(order_by_criteria)


def _get_query_fields(dbm):
    fields, old_labels, codes = get_entity_type_fields(dbm)
    fields.append("devices")
    fields.append('projects')
    # fields.append('groups')
    return fields


def _add_search_filters(search_filter_param, query_fields, search):
    if not search_filter_param:
        return search

    query_text = search_filter_param.get("search_text")
    if query_text:
        query_text_escaped = ElasticUtilsHelper().replace_special_chars(query_text)
        search = search.query("query_string", query=query_text_escaped, fields=query_fields)

    group_name = search_filter_param.get('group_name')
    if group_name:
        search = search.query("term", customgroup_value=group_name.lower())
    project_name = search_filter_param.get('project_name')
    if project_name:
        search = search.query("term", projects_value=project_name.lower())
    return search


def _add_filters(dbm, search_parameters, search):
    query_fields = _get_query_fields(dbm)
    search = _add_search_filters(search_parameters.get('search_filters'), query_fields,
                                 search)
    return query_fields, search


def get_data_sender_without_group_filters_count(dbm):
    es = Elasticsearch()
    search = Search(using=es, index=dbm.database_name, doc_type=REPORTER_DOC_TYPE)
    body = search.to_dict()
    return es.search(index=dbm.database_name, doc_type=REPORTER_DOC_TYPE, body=body, search_type='count')['hits']['total']


def get_data_sender_count(dbm, search_parameters):
    es = Elasticsearch()
    search = Search(using=es, index=dbm.database_name, doc_type=REPORTER_DOC_TYPE)
    query_fields, search = _add_filters(dbm, search_parameters, search)
    body = search.to_dict()
    return es.search(index=dbm.database_name, doc_type=REPORTER_DOC_TYPE, body=body, search_type='count')['hits']['total']


def get_datasenders(dbm, search_parameters):
    es = Elasticsearch()
    search = Search(using=es, index=dbm.database_name, doc_type=REPORTER_DOC_TYPE)
    search = _add_pagination_criteria(search_parameters, search)
    search = _add_sort_criteria(search_parameters, search)
    search = _add_response_fields(search_parameters, search)
    query_fields, search = _add_filters(dbm, search_parameters, search)
    datasenders = search.execute()
    return query_fields, datasenders
