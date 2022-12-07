from django.conf import settings


class BaseDatasource(object):
    def set_order(self, order_ref, asc):
        pass

    def set_limit(self, start, offset):
        pass

    def count(self):
        pass


class SqlDataSource(BaseDatasource):
    def __init__(self, sql):
        self.sql = sql


class QSDataSource(BaseDatasource):
    def __init__(self, qs, primary_key='pk'):
        self.qs = qs
        self.primary_key = primary_key

    def __iter__(self):
        return iter(self.qs)

    def __getitem__(self, item):
        if isinstance(item, slice):
            qs = self._clone()
            return qs[item]
        raise KeyError

    def __item__(self, key):
        pass

    def set_order(self, order_ref, asc):
        order_refs = [order_ref]
        if self.primary_key:
            order_refs.append(self.primary_key)
        if asc:
            self.qs = self.qs.order_by(*order_refs)
        else:
            self.qs = self.qs.order_by(*['-%s' % item for item in order_refs])

    def set_limit(self, start, offset):
        self.qs = self.qs[start:offset]

    def count(self):
        try:
            return self.qs.count()
        except AttributeError:
            return len(list(self.qs))

    def filter(self, *kargs, **kwargs):
        self.qs = self.qs.filter(*kargs, **kwargs)
        return self

    def distinct(self, base):
        if settings.DATABASES[self.qs.db]["ENGINE"] == "django.db.backends.oracle":
            # distinct analogue for Oracle users
            self.qs = base.filter(pk__in=set(self.qs.values_list('pk', flat=True)))
        else:
            self.qs = self.qs.distinct()
        return self

    def exclude(self, *kargs, **kwargs):
        self.qs = self.qs.exclude(*kargs, **kwargs)
        return self
        
    def extra(self, *kargs, **kwargs):
        self.qs = self.qs.extra(*kargs, **kwargs)
        return self

    def _clone(self, *args, **kwargs):
        if hasattr(self.qs, 'clone') and callable(self.qs.clone):
            return self.qs.clone()
        else:
            return self.qs.all(*args, **kwargs)
