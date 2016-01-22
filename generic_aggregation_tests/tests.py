import datetime

from django.conf import settings
from django.db import models
from django.test import TestCase

from generic_aggregation import generic_annotate as _generic_annotate, generic_aggregate as _generic_aggregate, generic_filter as _generic_filter
from generic_aggregation.utils import fallback_generic_annotate, fallback_generic_aggregate, fallback_generic_filter
from generic_aggregation_tests.models import (
    Food, Rating, CharFieldGFK
)

class SimpleTest(TestCase):
    PAST_DATE = datetime.datetime(2010, 1, 1)

    def setUp(self):
        self.apple = Food.objects.create(name='apple')
        self.orange = Food.objects.create(name='orange')
        self.peach = Food.objects.create(name='peach')

        Rating.objects.create(content_object=self.apple, rating=5)
        Rating.objects.create(content_object=self.apple, rating=3)
        Rating.objects.create(content_object=self.apple, rating=1,
                              created=self.PAST_DATE)
        Rating.objects.create(content_object=self.apple, rating=3,
                              created=self.PAST_DATE)

        Rating.objects.create(content_object=self.orange, rating=4)
        Rating.objects.create(content_object=self.orange, rating=3)
        Rating.objects.create(content_object=self.orange, rating=8,
                              created=self.PAST_DATE)

    def generic_annotate(self, *args, **kwargs):
        return _generic_annotate(*args, **kwargs)

    def generic_aggregate(self, *args, **kwargs):
        return _generic_aggregate(*args, **kwargs)

    def generic_filter(self, *args, **kwargs):
        return _generic_filter(*args, **kwargs)

    def test_annotation(self):
        annotated_qs = self.generic_annotate(
            Food.objects.all(),
            Rating.objects.all(),
            models.Count('ratings__rating')).order_by('-score')
        self.assertEqual(annotated_qs.count(), 3)

        food_a, food_b, food_c = annotated_qs

        self.assertEqual(food_a.score, 4)
        self.assertEqual(food_a.name, 'apple')

        self.assertEqual(food_b.score, 3)
        self.assertEqual(food_b.name, 'orange')

        self.assertEqual(food_c.score, 0)
        self.assertEqual(food_c.name, 'peach')

        annotated_qs = self.generic_annotate(Food.objects.all(), Rating, models.Sum('ratings__rating'))
        self.assertEqual(annotated_qs.count(), 3)

        if settings.NULLS_ASC_SORT_FIRST:
            food_b, food_a, food_c = annotated_qs.order_by('-score')
        else:
            food_c, food_b, food_a = annotated_qs.order_by('-score')

        self.assertEqual(food_b.score, 15)
        self.assertEqual(food_b.name, 'orange')

        self.assertEqual(food_a.score, 12)
        self.assertEqual(food_a.name, 'apple')

        self.assertEqual(food_c.score, None)
        self.assertEqual(food_c.name, 'peach')

        annotated_qs = self.generic_annotate(Food, Rating, models.Avg('ratings__rating'))
        self.assertEqual(annotated_qs.count(), 3)

        if settings.NULLS_ASC_SORT_FIRST:
            food_b, food_a, food_c = annotated_qs.order_by('-score')
        else:
            food_c, food_b, food_a = annotated_qs.order_by('-score')

        self.assertEqual(food_b.score, 5)
        self.assertEqual(food_b.name, 'orange')

        self.assertEqual(food_a.score, 3)
        self.assertEqual(food_a.name, 'apple')

        self.assertEqual(food_c.score, None)
        self.assertEqual(food_c.name, 'peach')

    def test_aggregation(self):
        # number of ratings on any food
        aggregated = self.generic_aggregate(Food, Rating, models.Count('ratings__rating'))
        self.assertEqual(aggregated, 7)

        # total of ratings out there for all foods
        aggregated = self.generic_aggregate(Food.objects.all(), Rating, models.Sum('ratings__rating'))
        self.assertEqual(aggregated, 27)

        # (showing the use of filters and inner query)

        aggregated = self.generic_aggregate(Food.objects.filter(name='apple'), Rating, models.Count('ratings__rating'))
        self.assertEqual(aggregated, 4)

        aggregated = self.generic_aggregate(Food.objects.filter(name='orange'), Rating, models.Count('ratings__rating'))
        self.assertEqual(aggregated, 3)

        # avg for apple
        aggregated = self.generic_aggregate(Food.objects.filter(name='apple'), Rating, models.Avg('ratings__rating'))
        self.assertEqual(aggregated, 3)

        # avg for orange
        aggregated = self.generic_aggregate(Food.objects.filter(name='orange'), Rating, models.Avg('ratings__rating'))
        self.assertEqual(aggregated, 5)

    def test_subset_annotation(self):
        todays_ratings = Rating.objects.filter(created__gte=datetime.date.today())
        annotated_qs = self.generic_annotate(Food.objects.all(), todays_ratings, models.Sum('ratings__rating'))
        self.assertEqual(annotated_qs.count(), 3)

        if settings.NULLS_ASC_SORT_FIRST:
            food_a, food_b, food_c = annotated_qs.order_by('-score')
        else:
            food_c, food_a, food_b = annotated_qs.order_by('-score')

        self.assertEqual(food_a.score, 8)
        self.assertEqual(food_a.name, 'apple')

        self.assertEqual(food_b.score, 7)
        self.assertEqual(food_b.name, 'orange')

        self.assertEqual(food_c.score, None)
        self.assertEqual(food_c.name, 'peach')

        persimmon = Food.objects.create(name='persimmon')

        Rating.objects.create(content_object=persimmon, rating=1,
                              created=self.PAST_DATE)

        self.assertEqual(annotated_qs.count(), 4)
        self.assertEqual(
            {'apple': 8, 'orange': 7, 'peach': None, 'persimmon': None},
            {food.name: food.score for food in annotated_qs})

    def test_subset_aggregation(self):
        todays_ratings = Rating.objects.filter(created__gte=datetime.date.today())
        aggregated = self.generic_aggregate(Food.objects.all(), todays_ratings, models.Sum('ratings__rating'))
        self.assertEqual(aggregated, 15)

        aggregated = self.generic_aggregate(Food.objects.all(), todays_ratings, models.Count('ratings__rating'))
        self.assertEqual(aggregated, 4)

    def test_charfield_pks(self):
        a1 = CharFieldGFK.objects.create(name='a1', content_object=self.apple)
        a2 = CharFieldGFK.objects.create(name='a2', content_object=self.apple)
        o1 = CharFieldGFK.objects.create(name='o1', content_object=self.orange)

        annotated_qs = self.generic_annotate(Food.objects.all(), CharFieldGFK, models.Count('char_gfk__name'))
        self.assertEqual(annotated_qs.count(), 3)

        food_a, food_b, food_c = annotated_qs.order_by('-score')

        self.assertEqual(food_b.score, 1)
        self.assertEqual(food_b.name, 'orange')

        self.assertEqual(food_a.score, 2)
        self.assertEqual(food_a.name, 'apple')

        self.assertEqual(food_c.score, 0)
        self.assertEqual(food_c.name, 'peach')

        aggregated = self.generic_aggregate(Food.objects.all(), CharFieldGFK, models.Count('char_gfk__name'))
        self.assertEqual(aggregated, 3)

    def test_custom_alias(self):
        annotated_qs = self.generic_annotate(Food, Rating, models.Count('ratings__rating'), alias='count')
        food_a, food_b, food_c = annotated_qs.order_by('-count')

        self.assertEqual(food_a.count, 4)
        self.assertEqual(food_a.name, 'apple')
        self.assertEqual(food_b.count, 3)
        self.assertEqual(food_b.name, 'orange')
        self.assertEqual(food_c.count, 0)
        self.assertEqual(food_c.name, 'peach')

    def test_filter(self):
        ratings = self.generic_filter(Rating.objects.all(), Food.objects.filter(name='orange'))
        self.assertEqual(len(ratings), 3)

        for obj in ratings:
            self.assertEqual(obj.content_object.name, 'orange')

    def test_filter_cast(self):
        a1 = CharFieldGFK.objects.create(name='a1', content_object=self.apple)
        a2 = CharFieldGFK.objects.create(name='a2', content_object=self.apple)
        o1 = CharFieldGFK.objects.create(name='o1', content_object=self.orange)

        qs = self.generic_filter(CharFieldGFK.objects.all(), Food.objects.filter(name='apple'))
        self.assertEqual(len(qs), 2)

        for obj in qs:
            self.assertEqual(obj.content_object.name, 'apple')

class FallbackTestCase(SimpleTest):
    def generic_annotate(self, *args, **kwargs):
        return fallback_generic_annotate(*args, **kwargs)

    def generic_aggregate(self, *args, **kwargs):
        return fallback_generic_aggregate(*args, **kwargs)

    def generic_filter(self, *args, **kwargs):
        return fallback_generic_filter(*args, **kwargs)
