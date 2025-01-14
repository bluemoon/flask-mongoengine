"""
Tools for generating forms based on mongoengine Document schemas.
"""
import inspect
from wtforms import fields as f, validators

from flaskext.mongoengine.wtf.fields import ModelSelectField
from flaskext.mongoengine.wtf.models import ModelForm

__all__ = (
    'model_fields', 'model_form',
)


def converts(*args):
    def _inner(func):
        func._converter_for = frozenset(args)
        return func
    return _inner


class ModelConverter():
    def __init__(self, converters=None):

        if not converters:
            converters = {}

        for name in dir(self):
            obj = getattr(self, name)
            if hasattr(obj, '_converter_for'):
                for classname in obj._converter_for:
                    converters[classname] = obj

        self.converters = converters

    def convert(self, model, field, field_args):
        kwargs = {
            'label': field.name,
            'description': '',
            'validators': [],
            'filters': [],
            'default': field.default,
        }
        if field_args:
            kwargs.update(field_args)

        if field.required:
            kwargs['validators'].append(validators.Required())

        if field.choices:
            kwargs['choices'] = field.choices
            return f.SelectField(**kwargs)

        ftype = type(field).__name__

        if hasattr(field, 'to_form_field'):
            return field.to_form_field(model, kwargs)

        if ftype in self.converters:
            return self.converters[ftype](model, field, kwargs)

    @classmethod
    def _string_common(cls, model, field, kwargs):
        if field.max_length or field.min_length:
            kwargs['validators'].append(
                validators.Length(max=field.max_length or - 1,
                                  min=field.min_length or - 1))

    @classmethod
    def _number_common(cls, model, field, kwargs):
        if field.max_value or field.min_value:
            kwargs['validators'].append(
                validators.NumberRange(max=field.max_value,
                                       min=field.min_value))

    @converts('StringField')
    def conv_String(self, model, field, kwargs):
        if field.regex:
            kwargs['validators'].append(validators.Regexp(regex=field.regex))
        self._string_common(model, field, kwargs)
        if field.max_length == -1:
            return f.TextAreaField(**kwargs)
        else:
            return f.TextField(**kwargs)

    @converts('URLField')
    def conv_URL(self, model, field, kwargs):
        kwargs['validators'].append(validators.URL())
        self._string_common(model, field, kwargs)
        return f.TextField(**kwargs)

    @converts('EmailField')
    def conv_Email(self, model, field, kwargs):
        kwargs['validators'].append(validators.Email())
        self._string_common(model, field, kwargs)
        return f.TextField(**kwargs)

    @converts('IntField')
    def conv_Int(self, model, field, kwargs):
        self._number_common(model, field, kwargs)
        return f.IntegerField(**kwargs)

    @converts('FloatField')
    def conv_Float(self, model, field, kwargs):
        self._number_common(model, field, kwargs)
        return f.FloatField(**kwargs)

    @converts('DecimalField')
    def conv_Decimal(self, model, field, kwargs):
        self._number_common(model, field, kwargs)
        return f.DecimalField(**kwargs)

    @converts('BooleanField')
    def conv_Boolean(self, model, field, kwargs):
        return f.BooleanField(**kwargs)

    @converts('DateTimeField')
    def conv_DateTime(self, model, field, kwargs):
        return f.DateTimeField(**kwargs)

    @converts('BinaryField')
    def conv_Binary(self, model, field, kwargs):
        #TODO: may be set file field that will save file`s data to MongoDB
        if field.max_bytes:
            kwargs['validators'].append(validators.Length(max=field.max_bytes))
        return f.TextAreaField(**kwargs)

    @converts('DictField')
    def conv_Dict(self, model, field, kwargs):
        return f.TextAreaField(**kwargs)

    @converts('ListField')
    def conv_List(self, model, field, kwargs):
        kwargs = {
            'validators': [],
            'filters': [],
        }
        unbound_field = self.convert(model, field.field, {})
        return f.FieldList(unbound_field, min_entries=0, **kwargs)

    @converts('SortedListField')
    def conv_SortedList(self, model, field, kwargs):
        #TODO: sort functionality, may be need sortable widget
        return self.conv_List(model, field, kwargs)

    @converts('GeoLocationField')
    def conv_GeoLocation(self, model, field, kwargs):
        #TODO: create geo field and widget (also GoogleMaps)
        return

    @converts('ObjectIdField')
    def conv_ObjectId(self, model, field, kwargs):
        return

    @converts('EmbeddedDocumentField')
    def conv_EmbeddedDocument(self, model, field, kwargs):
        kwargs = {
            'validators': [],
            'filters': [],
        }
        form_class = model_form(field.document_type_obj, field_args={})
        return f.FormField(form_class, **kwargs)

    @converts('ReferenceField')
    def conv_Reference(self, model, field, kwargs):
        return ModelSelectField(model=field.document_type, **kwargs)

    @converts('GenericReferenceField')
    def conv_GenericReference(self, model, field, kwargs):
        return


def model_fields(model, only=None, exclude=None, field_args=None, converter=None):
    """
    Generate a dictionary of fields for a given Django model.

    See `model_form` docstring for description of parameters.
    """
    from mongoengine.base import BaseDocument
    if BaseDocument not in inspect.getmro(model):
        raise TypeError('model must be a mongoengine Document schema')

    converter = converter or ModelConverter()
    field_args = field_args or {}

    if hasattr(model, '_fields_order'):
        field_names = model._fields_order
    else:
        field_names = model._fields.keys()

    if only:
        field_names = (x for x in field_names if x in only)
    elif exclude:
        field_names = (x for x in field_names if x not in exclude)

    field_dict = {}
    for name in field_names:
        model_field = model._fields[name]
        field = converter.convert(model, model_field, field_args.get(name))
        if field is not None:
            field_dict[name] = field

    return field_dict


def model_form(model, base_class=ModelForm, only=None, exclude=None, field_args=None, converter=None):
    """
    Create a wtforms Form for a given mongoengine Document schema::

        from flaskext.mongoengine.wtf import model_form
        from myproject.myapp.schemas import Article
        ArticleForm = model_form(Article)

    :param model:
        A mongoengine Document schema class
    :param base_class:
        Base form class to extend from. Must be a ``wtforms.Form`` subclass.
    :param only:
        An optional iterable with the property names that should be included in
        the form. Only these properties will have fields.
    :param exclude:
        An optional iterable with the property names that should be excluded
        from the form. All other properties will have fields.
    :param field_args:
        An optional dictionary of field names mapping to keyword arguments used
        to construct each field object.
    :param converter:
        A converter to generate the fields based on the model properties. If
        not set, ``ModelConverter`` is used.
    """
    field_dict = model_fields(model, only, exclude, field_args, converter)
    field_dict['model_class'] = model
    return type(model.__name__ + 'Form', (base_class,), field_dict)
