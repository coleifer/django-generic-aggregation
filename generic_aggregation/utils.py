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

def prepare_query(qs_model, generic_qs_model, aggregator, gfk_field):
    qs = normalize_qs_model(qs_model)
    generic_qs = normalize_qs_model(generic_qs_model)
    
    if gfk_field is None:
        gfk_field = get_gfk_field(generic_qs.model)
    
    content_type = ContentType.objects.get_for_model(qs.model)
    rel_name = aggregator.lookup.split('__', 1)[0]
    
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
    
    Example:
    
    generic_annotate(Food.objects.all(), Rating.objects.all(), Avg('ratings__rating'))
    """
    prepared_query = prepare_query(qs_model, generic_qs_model, aggregator, gfk_field)
    return prepared_query.annotate(**{alias: aggregator})


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
    
    Example:
    
    generic_annotate(Food.objects.all(), Rating.objects.all(), Avg('ratings__rating'))
    """
    prepared_query = prepare_query(qs_model, generic_qs_model, aggregator, gfk_field)
    return prepared_query.aggregate(aggregate=aggregator)['aggregate']


def generic_filter(generic_qs_model, filter_qs_model, gfk_field=None):
    """
    Filter a queryset of objects containing GFKs so that they are restricted to
    only those objects that relate to items in the filter queryset
    """
    generic_qs = normalize_qs_model(generic_qs_model)
    filter_qs = normalize_qs_model(filter_qs_model)
    
    if not gfk_field:
        gfk_field = get_gfk_field(generic_qs.model)
    
    return generic_qs.filter(**{
        gfk_field.ct_field: ContentType.objects.get_for_model(filter_qs.model),
        '%s__in' % gfk_field.fk_field: filter_qs.values('pk'),
    })
