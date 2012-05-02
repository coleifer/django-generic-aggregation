==========================
django-generic-aggregation
==========================

annotate() and aggregate() for generically-related data.  also a handy function
for filtering GFK-model querysets.

the use of annotate() and aggregate() require a ``GenericRelation``.

Examples
--------

You want the most commented on blog entries::

    >>> from django.contrib.comments.models import Comment
    >>> from django.db.models import Count
    >>> from blog.models import BlogEntry
    >>> from generic_aggregation import generic_annotate

    >>> annotated = generic_annotate(BlogEntry.objects.all(), Comment, Count('comments__id'))

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

    >>> aggregate = generic_aggregate(Food, Rating, Sum('ratings__rating'))
    >>> print aggregate
    15

    >>> aggregate = generic_aggregate(Food, Rating.objects.all(), Avg('ratings__rating'))
    >>> print aggregate
    5

You want to only display ratings for comments made on a given site:

    >>> from django.contrib.comments.models import Comment
    >>> from generic_aggregation import generic_filter
    >>> ratings = Rating.objects.all() # <--- grab all the ratings
    >>> comments = Comment.objects.filter(site=Site.objects.get_current())
    >>> siteified_ratings = generic_filter(ratings, comments)

Check the tests - there are more examples there.  Tested with postgres & sqlite
