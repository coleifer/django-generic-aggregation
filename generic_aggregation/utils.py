"""
Django does not properly set up casts
"""

import django
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import connection
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
    raw_type = f.db_type(connection)
    if raw_type.lower().split()[0] in ('serial', 'integer', 'unsigned', 'bigint', 'smallint'):
        raw_type = 'integer'
    return raw_type

def generic_annotate(qs_model, generic_qs_model, aggregator, gfk_field=None, alias='score'):
    """
    Find blog entries with the most comments:
    
        qs = generic_annotate(Entry.objects.public(), Comment.objects.public(), Count('comments__id'))
        for entry in qs:
            print entry.title, entry.score
    
    Find the highest rated foods:
    
        generic_annotate(Food, Rating, Avg('ratings__rating'), alias='avg')
        for food in qs:
            print food.name, '- average rating:', food.avg
    
    .. note::
        In both of the above examples it is assumed that a GenericRelation exists
        on Entry to Comment (named "comments") and also on Food to Rating (named "ratings").
        If a GenericRelation does *not* exist, the query will still return correct
        results but the code path will be different as it will use the fallback method.
    
    .. warning::
        If the underlying column type differs between the qs_model's primary
        key and the generic_qs_model's foreign key column, it will use the fallback
        method, which can correctly CASTself.
    
    :param qs_model: A model or a queryset of objects you want to perform
        annotation on, e.g. blog entries
    :param generic_qs_model: A model or queryset containing a GFK, e.g. comments
    :param aggregator: an aggregation, from django.db.models, e.g. Count('id') or Avg('rating')
    :param gfk_field: explicitly specify the field w/the gfk
    :param alias: attribute name to use for annotation
    """
    return fallback_generic_annotate(qs_model, generic_qs_model, aggregator, gfk_field, alias)


def generic_aggregate(qs_model, generic_qs_model, aggregator, gfk_field=None):
    """
    Find total number of comments on blog entries:
    
        generic_aggregate(Entry.objects.public(), Comment.objects.public(), Count('comments__id'))
    
    Find the average rating for foods starting with 'a':
    
        a_foods = Food.objects.filter(name__startswith='a')
        generic_aggregate(a_foods, Rating, Avg('ratings__rating'))
    
    .. note::
        In both of the above examples it is assumed that a GenericRelation exists
        on Entry to Comment (named "comments") and also on Food to Rating (named "ratings").
        If a GenericRelation does *not* exist, the query will still return correct
        results but the code path will be different as it will use the fallback method.
    
    .. warning::
        If the underlying column type differs between the qs_model's primary
        key and the generic_qs_model's foreign key column, it will use the fallback
        method, which can correctly CASTself.

    :param qs_model: A model or a queryset of objects you want to perform
        annotation on, e.g. blog entries
    :param generic_qs_model: A model or queryset containing a GFK, e.g. comments
    :param aggregator: an aggregation, from django.db.models, e.g. Count('id') or Avg('rating')
    :param gfk_field: explicitly specify the field w/the gfk
    """
    return fallback_generic_aggregate(qs_model, generic_qs_model, aggregator, gfk_field)


def generic_filter(generic_qs_model, filter_qs_model, gfk_field=None):
    """
    Only show me ratings made on foods that start with "a":
    
        a_foods = Food.objects.filter(name__startswith='a')
        generic_filter(Rating.objects.all(), a_foods)
    
    Only show me comments from entries that are marked as public:
    
        generic_filter(Comment.objects.public(), Entry.objects.public())
    
    :param generic_qs_model: A model or queryset containing a GFK, e.g. comments
    :param qs_model: A model or a queryset of objects you want to restrict the generic_qs to
    :param gfk_field: explicitly specify the field w/the gfk
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
    return query.get_compiler(connection=connection).as_sql()

def query_as_nested_sql(query):
    return query.get_compiler(connection=connection).as_nested_sql()

def gfk_expression(qs_model, gfk_field):
    # handle casting the GFK field if need be
    qn = connection.ops.quote_name
    
    pk_field_type = get_field_type(qs_model._meta.pk)
    gfk_field_type = get_field_type(gfk_field.model._meta.get_field(gfk_field.fk_field))
    if 'mysql' in connection.settings_dict['ENGINE'] and pk_field_type == 'integer':
        pk_field_type = 'unsigned'
    
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

    if django.VERSION < (1, 8):
        aggregate_field = aggregator.lookup
    else:
        aggregate_field = aggregator.default_alias.rsplit('__', 1)[0]

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
        SELECT %s(%s) AS aggregate_score
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

    if django.VERSION < (1, 8):
        aggregate_field = aggregator.lookup
    else:
        aggregate_field = aggregator.default_alias.rsplit('__', 1)[0]
    
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
