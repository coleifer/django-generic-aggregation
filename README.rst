==========================
django-generic-aggregation
==========================

annotate() and aggregate() for generically-related data.

Examples
--------

You want the most commented on blog entries::

    >>> from django.contrib.comments.models import Comment
    >>> from django.db.models import Count
    >>> from blog.models import BlogEntry
    >>> from generic_aggregation import generic_annotate

    >>> annotated = generic_annotate(BlogEntry.objects.all(), Comment.content_object, Count('id'))

    >>> for entry in annotated:
    ...    print entry.title, entry.score

    The most popular 5
    The second best 4
    Nobody commented 0


You want to figure out which items are highest rated::

    from django.db.models import Sum, Avg

    # assume a Food model and a generic Rating model
    apple = Food.objects.create(name='apple')
    
    # create some ratings on the food
    Rating.objects.create(content_object=apple, rating=3)
    Rating.objects.create(content_object=apple, rating=5)
    Rating.objects.create(content_object=apple, rating=7)

    >>> aggregate = generic_aggregate(Food.objects.all(), Rating.content_object, Sum('rating'))
    >>> print aggregate
    15

    >>> aggregate = generic_aggregate(Food.objects.all(), Rating.content_object, Avg('rating'))
    >>> print aggregate
    5


Check the tests - there are more examples there.  Tested with postgres & sqlite
