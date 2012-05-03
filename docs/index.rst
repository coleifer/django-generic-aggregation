.. django-generic-aggregation documentation master file, created by
   sphinx-quickstart on Wed May  2 16:49:11 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==========================
django-generic-aggregation
==========================

annotate() and aggregate() for generically-related data.  also a handy function
for filtering GFK-model querysets.

.. note::
    Use django's `GenericRelation <https://docs.djangoproject.com/en/dev/ref/contrib/contenttypes/#reverse-generic-relations>`_ where possible,
    as this can make the queries generated more efficient by using a JOIN rather
    than a subquery.


installation
------------

::

    # install from pypi
    pip install django-generic-aggregation
    
    # or install via git
    pip install -e git+git://github.com/coleifer/django-generic-aggregation.git#egg=generic_aggregation


examples
--------

The examples below assume the following simple models:

.. code-block:: python

    class Rating(models.Model):
        rating = models.IntegerField()
        object_id = models.IntegerField()
        content_type = models.ForeignKey(ContentType)
        content_object = GenericForeignKey(ct_field='content_type', fk_field='object_id')
    
    class Food(models.Model):
        name = models.CharField(max_length=50)
        ratings = generic.GenericRelation(Rating) # reverse generic relation


You want to figure out which items are highest rated (:py:func:`~generic_aggregation.generic_annotate`)

.. code-block:: python

    from django.db.models import Avg
    
    food_qs = Food.objects.filter(name__startswith='a')
    generic_annotate(food_qs, Rating, Avg('ratings__rating'))
    
    # you can mix and match queryset / model
    generic_annotate(food_qs, Rating.objects.all(), Avg('ratings__rating'))

You want the average rating for all foods that start with 'a' (:py:func:`~generic_aggregation.generic_aggregate`)

.. code-block:: python

    food_qs = Food.objects.filter(name__startswith='a')
    generic_aggregate(food_qs, Rating, Avg('ratings__rating'))

You want to only display ratings for foods that start with 'a' (:py:func:`~generic_aggregation.generic_filter`)

    food_qs = Food.objects.filter(name__startswith='a')
    generic_filter(Rating.objects.all(), food_qs)


important detail
----------------

As you may have noted in the above examples (at least those using annotate and
aggregate), the aggregate we pass in is prefixed with ``ratings__``.  The double-underscore
prefix refers to the ``ratings`` attribute of the Food model, which is a
``django.contrib.contenttypes.generic.GenericRelation`` instance.  We are querying
*across* that relation to the field on the Ratings model that we are interested in.
When possible, use a GenericRelation and construct your queries in this manner.

If you do not have a GenericRelation on the model being queried, it will use
a "fallback" method that will return the correct results, though queried in a slightly
different manner (a subquery will be used as opposed to a left outer join).

If for some reason the Generic Foreign Key's "object_id" field is of a different
type than the Primary Key of the related model -- which is probably the case if you're
using django.contrib.comments, as it uses a TextField -- a ``CAST`` expression is
required by some RDBMS'.  Django will not put it there for you, so again, the
code will use the "fallback" methods in this case, which add the necessary ``CAST``.

`View the code <https://github.com/coleifer/django-generic-aggregation/>`_ for the nitty-gritty details.


api
---

.. py:module:: generic_aggregation

.. py:function:: generic_annotate(qs_model, generic_qs_model, aggregator[, gfk_field=None[, alias='score']])

    Find blog entries with the most comments:
    
    .. code-block:: python
    
        qs = generic_annotate(Entry.objects.public(), Comment.objects.public(), Count('comments__id'))
        for entry in qs:
            print entry.title, entry.score
    
    Find the highest rated foods:

    .. code-block:: python
    
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
    :rtype: a queryset containing annotate rows

.. py:function:: generic_aggregate(qs_model, generic_qs_model, aggregator[, gfk_field=None])

    Find total number of comments on blog entries:
    
    .. code-block:: python
    
        generic_aggregate(Entry.objects.public(), Comment.objects.public(), Count('comments__id'))
    
    Find the average rating for foods starting with 'a':
    
    .. code-block:: python
    
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
    :rtype: a scalar value indicating the result of the aggregation

.. py:function:: generic_filter(generic_qs_model, filter_qs_model[, gfk_field=None])

    Only show me ratings made on foods that start with "a":
    
        a_foods = Food.objects.filter(name__startswith='a')
        generic_filter(Rating.objects.all(), a_foods)
    
    Only show me comments from entries that are marked as public:
    
        generic_filter(Comment.objects.public(), Entry.objects.public())
    
    :param generic_qs_model: A model or queryset containing a GFK, e.g. comments
    :param qs_model: A model or a queryset of objects you want to restrict the generic_qs to
    :param gfk_field: explicitly specify the field w/the gfk
    :rtype: a filtered queryset


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

