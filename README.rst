==========================
django-generic-aggregation
==========================

annotate() and aggregate() for generically-related data.  also a handy function
for filtering GFK-model querysets.

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

::

    class Rating(models.Model):
        rating = models.IntegerField()
        object_id = models.IntegerField()
        content_type = models.ForeignKey(ContentType)
        content_object = GenericForeignKey(ct_field='content_type', fk_field='object_id')
    
    class Food(models.Model):
        name = models.CharField(max_length=50)
        ratings = generic.GenericRelation(Rating) # reverse generic relation


You want to figure out which items are highest rated (generic_annotate)

::

    from django.db.models import Avg
    
    food_qs = Food.objects.filter(name__startswith='a')
    generic_annotate(food_qs, Rating, Avg('ratings__rating'))
    
    # you can mix and match queryset / model
    generic_annotate(food_qs, Rating.objects.all(), Avg('ratings__rating'))

You want the average rating for all foods that start with 'a' (generic_aggregate)

::

    food_qs = Food.objects.filter(name__startswith='a')
    generic_aggregate(food_qs, Rating, Avg('ratings__rating'))

You want to only display ratings for foods that start with 'a' (generic_filter)

    food_qs = Food.objects.filter(name__startswith='a')
    generic_filter(Rating.objects.all(), food_qs)


documentation
-------------

http://django-generic-aggregation.readthedocs.org/
