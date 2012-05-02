"""
Django does not properly set up casts
"""

import django
from django.contrib.contenttypes.generic import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import connection, models
from django.db.models.query import QuerySet


def get_gfk_field(model):
    for field in model._meta.virtual_fields:
        if isinstance(field, GenericForeignKey):
            return field

    raise ValueError('Unable to find gfk field on %s' % model)

def normalize_qs_model(qs_or_model):
    if isinstance(qs_or_model, QuerySet):
        return qs_or_model
    return qs_or_model._default_manager.all()

def get_field_type(f):
    if django.VERSION < (1, 4):
        raw_type = f.db_type()
    else:
        raw_type = f.db_type(connection)
    if raw_type.lower().split()[0] in ('serial', 'integer', 'unsigned', 'bigint', 'smallint'):
        raw_type = 'integer'
    return raw_type

def prepare_query(qs_model, generic_qs_model, aggregator, gfk_field):
    qs = normalize_qs_model(qs_model)
    generic_qs = normalize_qs_model(generic_qs_model)
    
    model = qs.model
    generic_model = generic_qs.model
    
    if gfk_field is None:
        gfk_field = get_gfk_field(generic_model)
    
    content_type = ContentType.objects.get_for_model(model)
    rel_name = aggregator.lookup.split('__', 1)[0]
    
    try:
        generic_rel_descriptor = getattr(model, rel_name)
    except AttributeError:
        # missing the generic relation, so do fallback query
        return False
    
    rel_model = generic_rel_descriptor.field.rel.to
    if rel_model != generic_model:
        raise AttributeError('Model %s does not match the GenericRelation "%s" (%s)' % (
            generic_model, rel_name, rel_model,
        ))
    
    pk_field_type = get_field_type(model._meta.pk)
    gfk_field_type = get_field_type(generic_model._meta.get_field(gfk_field.fk_field))
    if pk_field_type != gfk_field_type:
        return False
    
    qs = qs.filter(**{
        '%s__%s' % (rel_name, gfk_field.ct_field): content_type,
        '%s__pk__in' % (rel_name): generic_qs.values('pk'),
    })
    return qs

def generic_annotate(qs_model, generic_qs_model, aggregator, gfk_field=None, alias='score'):
    """
    :param qs_model: A model or a queryset of objects you want to perform
        annotation on, e.g. blog entries
    :param generic_qs_model: A model or queryset containing a GFK, e.g. comments
    :param aggregator: an aggregation, from django.db.models, e.g. Count('id') or Avg('rating')
    :param gfk_field: explicitly specify the field w/the gfk
    :param alias: attribute name to use for annotation
    
    Note:
        requires presence of a GenericRelation() on the qs_model, which should
        be referenced in the aggregator function
    
    Warning:
        if the primary key field differs in type from the GFK's fk_field a CAST
        is not expressed on the JOIN, so the code will fallback gracefully
    
    Example:
    
    generic_annotate(Food.objects.all(), Rating.objects.all(), Avg('ratings__rating'))
    """
    prepared_query = prepare_query(qs_model, generic_qs_model, aggregator, gfk_field)
    if prepared_query is not False:
        return prepared_query.annotate(**{alias: aggregator})
    else:
        # need to fall back since CAST will be missing
        return fallback_generic_annotate(qs_model, generic_qs_model, aggregator, gfk_field, alias)


def generic_aggregate(qs_model, generic_qs_model, aggregator, gfk_field=None):
    """
    :param qs_model: A model or a queryset of objects you want to perform
        annotation on, e.g. blog entries
    :param generic_qs_model: A model or queryset containing a GFK, e.g. comments
    :param aggregator: an aggregation, from django.db.models, e.g. Count('id') or Avg('rating')
    :param gfk_field: explicitly specify the field w/the gfk
    
    Note:
        requires presence of a GenericRelation() on the qs_model, which should
        be referenced in the aggregator function
    
    Warning:
        if the primary key field differs in type from the GFK's fk_field a CAST
        is not expressed on the JOIN, so the code will fallback gracefully
    
    Example:
    
    generic_annotate(Food.objects.all(), Rating.objects.all(), Avg('ratings__rating'))
    """
    prepared_query = prepare_query(qs_model, generic_qs_model, aggregator, gfk_field)
    if prepared_query is not False:
        return prepared_query.aggregate(aggregate=aggregator)['aggregate']
    else:
        # need to fall back since CAST will be missing
        return fallback_generic_aggregate(qs_model, generic_qs_model, aggregator, gfk_field)


def generic_filter(generic_qs_model, filter_qs_model, gfk_field=None):
    """
    Filter a queryset of objects containing GFKs so that they are restricted to
    only those objects that relate to items in the filter queryset
    """
    generic_qs = normalize_qs_model(generic_qs_model)
    filter_qs = normalize_qs_model(filter_qs_model)
    
    if not gfk_field:
        gfk_field = get_gfk_field(generic_qs.model)
    
    pk_field_type = get_field_type(filter_qs.model._meta.pk)
    gfk_field_type = get_field_type(generic_qs.model._meta.get_field(gfk_field.fk_field))
    if pk_field_type != gfk_field_type:
        return fallback_generic_filter(generic_qs, filter_qs, gfk_field)
    
    return generic_qs.filter(**{
        gfk_field.ct_field: ContentType.objects.get_for_model(filter_qs.model),
        '%s__in' % gfk_field.fk_field: filter_qs.values('pk'),
    })


###############################################################################
# fallback methods

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
    
    pk_field_type = get_field_type(qs_model._meta.pk)
    gfk_field_type = get_field_type(gfk_field.model._meta.get_field(gfk_field.fk_field))
    
    if pk_field_type != gfk_field_type:
        # cast the gfk to the pk type
        gfk_expr = "CAST(%s AS %s)" % (qn(gfk_field.fk_field), pk_field_type)
    else:
        gfk_expr = qn(gfk_field.fk_field) # the object_id field on the GFK
    
    return gfk_expr

def fallback_generic_annotate(qs_model, generic_qs_model, aggregator, gfk_field=None, alias='score'):
    qs = normalize_qs_model(qs_model)
    generic_qs = normalize_qs_model(generic_qs_model)
    
    content_type = ContentType.objects.get_for_model(qs.model)
    
    qn = connection.ops.quote_name
    aggregate_field = aggregator.lookup
    
    # since the aggregate may contain a generic relation, strip it
    if '__' in aggregate_field:
        _, aggregate_field = aggregate_field.rsplit('__', 1)
    
    if gfk_field is None:
        gfk_field = get_gfk_field(generic_qs.model)
    
    # collect the params we'll be using
    params = (
        aggregator.name, # the function that's doing the aggregation
        qn(aggregate_field), # the field containing the value to aggregate
        qn(gfk_field.model._meta.db_table), # table holding gfk'd item info
        qn(gfk_field.ct_field + '_id'), # the content_type field on the GFK
        content_type.pk, # the content_type id we need to match
        gfk_expression(qs.model, gfk_field),
        qn(qs.model._meta.db_table), # the table and pk from the main
        qn(qs.model._meta.pk.name)   # part of the query
    )
    
    sql_template = """
        SELECT COALESCE(%s(%s), 0) AS aggregate_score
        FROM %s
        WHERE
            %s=%s AND
            %s=%s.%s"""
    
    extra = sql_template % params
    
    if generic_qs.query.where.children:
        generic_query = generic_qs.values_list('pk').query
        inner_query, inner_query_params = query_as_sql(generic_query)
        
        inner_params = (
            qn(generic_qs.model._meta.db_table),
            qn(generic_qs.model._meta.pk.name),
        )
        inner_start = ' AND %s.%s IN (' % inner_params
        inner_end = ')'
        extra = extra + inner_start + inner_query + inner_end
    else:
        inner_query_params = []

    return qs.extra(
        select={alias: extra},
        select_params=inner_query_params,
    )

def fallback_generic_aggregate(qs_model, generic_qs_model, aggregator, gfk_field=None):
    qs = normalize_qs_model(qs_model)
    generic_qs = normalize_qs_model(generic_qs_model)
    
    content_type = ContentType.objects.get_for_model(qs.model)
    
    qn = connection.ops.quote_name
    aggregate_field = aggregator.lookup
    
    # since the aggregate may contain a generic relation, strip it
    if '__' in aggregate_field:
        _, aggregate_field = aggregate_field.rsplit('__', 1)
    
    if gfk_field is None:
        gfk_field = get_gfk_field(generic_qs.model)
    
    qs = qs.values_list('pk') # just the pks
    query, query_params = query_as_nested_sql(qs.query)
    
    # collect the params we'll be using
    params = (
        aggregator.name, # the function that's doing the aggregation
        qn(aggregate_field), # the field containing the value to aggregate
        qn(gfk_field.model._meta.db_table), # table holding gfk'd item info
        qn(gfk_field.ct_field + '_id'), # the content_type field on the GFK
        content_type.pk, # the content_type id we need to match
        gfk_expression(qs.model, gfk_field), # the object_id field on the GFK
    )
    
    query_start = """
        SELECT %s(%s) AS aggregate_score
        FROM %s
        WHERE
            %s=%s AND
            %s IN (
                """ % params
    
    query_end = ")"
    
    if generic_qs.query.where.children:
        generic_query = generic_qs.values_list('pk').query
        inner_query, inner_query_params = query_as_sql(generic_query)
        
        query_params += inner_query_params
        
        inner_params = (
            qn(generic_qs.model._meta.pk.name),
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

def fallback_generic_filter(generic_qs_model, filter_qs_model, gfk_field=None):
    generic_qs = normalize_qs_model(generic_qs_model)
    filter_qs = normalize_qs_model(filter_qs_model)
    
    if gfk_field is None:
        gfk_field = get_gfk_field(generic_qs.model)
    
    # get the contenttype of our filtered queryset, e.g. Business
    filter_model = filter_qs.model
    content_type = ContentType.objects.get_for_model(filter_model)
    
    # filter the generic queryset to only include items of the given ctype
    generic_qs = generic_qs.filter(**{gfk_field.ct_field: content_type})
    
    # just select the primary keys in the sub-select
    filtered_query = filter_qs.values_list('pk').query
    inner_query, inner_query_params = query_as_sql(filtered_query)
    
    where = '%s IN (%s)' % (
        gfk_expression(filter_model, gfk_field),
        inner_query,
    )
    
    return generic_qs.extra(
        where=(where,),
        params=inner_query_params
    )
