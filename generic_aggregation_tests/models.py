import datetime

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Rating(models.Model):
    rating = models.IntegerField()
    created = models.DateTimeField(default=datetime.datetime.now)
    object_id = models.IntegerField()
    content_type = models.ForeignKey(ContentType)
    content_object = GenericForeignKey(ct_field='content_type', fk_field='object_id')
    
    def __unicode__(self):
        return '%s rated %s' % (self.content_object, self.rating)


class CharFieldGFK(models.Model):
    name = models.CharField(max_length=255)
    object_id = models.TextField()
    content_type = models.ForeignKey(ContentType)
    content_object = GenericForeignKey(ct_field='content_type', fk_field='object_id')


class Food(models.Model):
    name = models.CharField(max_length=100)
    
    ratings = GenericRelation(Rating)
    char_gfk = GenericRelation(CharFieldGFK)

    def __unicode__(self):
        return self.name
