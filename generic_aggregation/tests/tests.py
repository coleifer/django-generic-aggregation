import datetime

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test import TestCase

from generic_aggregation import generic_annotate, generic_aggregate
from generic_aggregation.tests.models import Food, Rating

class SimpleTest(TestCase):
    def setUp(self):
        self.apple = Food.objects.create(name='apple')
        self.orange = Food.objects.create(name='orange')
        
        dt = datetime.datetime(2010, 1, 1)
        
        Rating.objects.create(content_object=self.apple, rating=5)
        Rating.objects.create(content_object=self.apple, rating=3)
        Rating.objects.create(content_object=self.apple, rating=1, created=dt)
        Rating.objects.create(content_object=self.apple, rating=3, created=dt)
        
        Rating.objects.create(content_object=self.orange, rating=4)
        Rating.objects.create(content_object=self.orange, rating=3)
        Rating.objects.create(content_object=self.orange, rating=8, created=dt)
        
    def test_annotation(self):
        annotated_qs = generic_annotate(Food.objects.all(), Rating.content_object, 'rating', models.Count)
        self.assertEqual(annotated_qs.count(), 2)
        
        food_a, food_b = annotated_qs
        
        self.assertEqual(food_a.score, 4)
        self.assertEqual(food_a.name, 'apple')
        
        self.assertEqual(food_b.score, 3)
        self.assertEqual(food_b.name, 'orange')
        
        annotated_qs = generic_annotate(Food.objects.all(), Rating.content_object, 'rating', models.Sum)
        self.assertEqual(annotated_qs.count(), 2)
        
        food_b, food_a = annotated_qs
        
        self.assertEqual(food_b.score, 15)
        self.assertEqual(food_b.name, 'orange')
        
        self.assertEqual(food_a.score, 12)
        self.assertEqual(food_a.name, 'apple')
        
        annotated_qs = generic_annotate(Food.objects.all(), Rating.content_object, 'rating', models.Avg)
        self.assertEqual(annotated_qs.count(), 2)
        
        food_b, food_a = annotated_qs
        
        self.assertEqual(food_b.score, 5)
        self.assertEqual(food_b.name, 'orange')
        
        self.assertEqual(food_a.score, 3)
        self.assertEqual(food_a.name, 'apple')
    
    def test_aggregation(self):
        # number of ratings on any food
        aggregated = generic_aggregate(Food.objects.all(), Rating.content_object, 'rating', models.Count)
        self.assertEqual(aggregated, 7)
        
        # total of ratings out there for all foods
        aggregated = generic_aggregate(Food.objects.all(), Rating.content_object, 'rating', models.Sum)
        self.assertEqual(aggregated, 27)
        
        # (showing the use of filters and inner query)
        
        aggregated = generic_aggregate(Food.objects.filter(name='apple'), Rating.content_object, 'rating', models.Count)
        self.assertEqual(aggregated, 4)
        
        aggregated = generic_aggregate(Food.objects.filter(name='orange'), Rating.content_object, 'rating', models.Count)
        self.assertEqual(aggregated, 3)
        
        # avg for apple
        aggregated = generic_aggregate(Food.objects.filter(name='apple'), Rating.content_object, 'rating', models.Avg)
        self.assertEqual(aggregated, 3)
        
        # avg for orange
        aggregated = generic_aggregate(Food.objects.filter(name='orange'), Rating.content_object, 'rating', models.Avg)
        self.assertEqual(aggregated, 5)
    
    def test_subset_annotation(self):
        todays_ratings = Rating.objects.filter(created__gte=datetime.date.today())
        annotated_qs = generic_annotate(Food.objects.all(), Rating.content_object, 'rating', models.Sum, todays_ratings)
        self.assertEqual(annotated_qs.count(), 2)
        
        food_a, food_b = annotated_qs

        self.assertEqual(food_a.score, 8)
        self.assertEqual(food_a.name, 'apple')
        
        self.assertEqual(food_b.score, 7)
        self.assertEqual(food_b.name, 'orange')
    
    def test_subset_aggregation(self):
        todays_ratings = Rating.objects.filter(created__gte=datetime.date.today())
        aggregated = generic_aggregate(Food.objects.all(), Rating.content_object, 'rating', models.Sum, todays_ratings)
        self.assertEqual(aggregated, 15)
        
        aggregated = generic_aggregate(Food.objects.all(), Rating.content_object, 'rating', models.Count, todays_ratings)
        self.assertEqual(aggregated, 4)
