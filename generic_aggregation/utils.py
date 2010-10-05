import django
from django.contrib.contenttypes.models import ContentType
from django.db import connection, models

def query_as_sql(query):
    if django.VERSION < (1, 2):
        return query.as_sql()
    else:
        return query.get_compiler(connection=connection).as_sql()

def query_as_nested_sql(query):
    if django.VERSION < (1, 2):
        return query.as_nested_sql()
    else:
        return query.get_compiler(connection=connection).as_nested_sql()

def gfk_expression(qs_model, gfk_field):
    # handle casting the GFK field if need be
    qn = connection.ops.quote_name
    
    pk_field_type = qs_model._meta.pk.db_type()
    gfk_field_type = gfk_field.model._meta.get_field(gfk_field.fk_field).db_type()
    
    if pk_field_type == 'serial':
        pk_field_type = 'integer'
    elif pk_field_type.lower() == 'integer auto_increment':
        pk_field_type = 'UNSIGNED'
    
    if pk_field_type != gfk_field_type:
        # cast the gfk to the pk type
        gfk_expr = "CAST(%s AS %s)" % (qn(gfk_field.fk_field), pk_field_type)
    else:
        gfk_expr = qn(gfk_field.fk_field) # the object_id field on the GFK
    
    return gfk_expr


def generic_annotate(queryset, gfk_field, aggregator, generic_queryset=None,
                     desc=True, alias='score'):
    ordering = desc and '-%s' % alias or alias
    content_type = ContentType.objects.get_for_model(queryset.model)
    
    qn = connection.ops.quote_name
    aggregate_field = aggregator.lookup
    
    # collect the params we'll be using
    params = (
        aggregator.name, # the function that's doing the aggregation
        qn(aggregate_field), # the field containing the value to aggregate
        qn(gfk_field.model._meta.db_table), # table holding gfk'd item info
        qn(gfk_field.ct_field + '_id'), # the content_type field on the GFK
        content_type.pk, # the content_type id we need to match
        gfk_expression(queryset.model, gfk_field),
        qn(queryset.model._meta.db_table), # the table and pk from the main
        qn(queryset.model._meta.pk.name)   # part of the query
    )
    
    sql_template = """
        SELECT %s(%s) AS aggregate_score
        FROM %s
        WHERE
            %s=%s AND
            %s=%s.%s"""
    
    extra = sql_template % params
    
    if generic_queryset is not None:
        generic_query = generic_queryset.values_list('pk').query
        inner_query, inner_query_params = query_as_sql(generic_query)
        
        inner_params = (
            qn(generic_queryset.model._meta.db_table),
            qn(generic_queryset.model._meta.pk.name),
        )
        inner_start = ' AND %s.%s IN (' % inner_params
        inner_end = ')'
        extra = extra + inner_start + inner_query + inner_end
    else:
        inner_query_params = []

    queryset = queryset.extra(
        select={alias: extra},
        select_params=inner_query_params,
        order_by=[ordering]
    )
    
    return queryset


def generic_aggregate(queryset, gfk_field, aggregator, generic_queryset=None):
    content_type = ContentType.objects.get_for_model(queryset.model)
    
    queryset = queryset.values_list('pk') # just the pks
    query, query_params = query_as_nested_sql(queryset.query)
    
    qn = connection.ops.quote_name
    aggregate_field = aggregator.lookup
    
    # collect the params we'll be using
    params = (
        aggregator.name, # the function that's doing the aggregation
        qn(aggregate_field), # the field containing the value to aggregate
        qn(gfk_field.model._meta.db_table), # table holding gfk'd item info
        qn(gfk_field.ct_field + '_id'), # the content_type field on the GFK
        content_type.pk, # the content_type id we need to match
        gfk_expression(queryset.model, gfk_field), # the object_id field on the GFK
    )
    
    query_start = """
        SELECT %s(%s) AS aggregate_score
        FROM %s
        WHERE
            %s=%s AND
            %s IN (
                """ % params
    
    query_end = ")"
    
    if generic_queryset is not None:
        generic_query = generic_queryset.values_list('pk').query
        inner_query, inner_query_params = query_as_sql(generic_query)
        
        query_params += inner_query_params
        
        inner_params = (
            qn(generic_queryset.model._meta.pk.name),
        )
        inner_start = ' AND %s IN (' % inner_params
        inner_end = ')'
        query_end = query_end + inner_start + inner_query + inner_end
    
    # pass in the inner_query unmodified as we will use the cursor to handle
    # quoting the inner parameters correctly
    query = query_start + query + query_end
    
    cursor = connection.cursor()
    cursor.execute(query, query_params)
    row = cursor.fetchone()

    return row[0]
