import redis
from django.conf import settings
from .models import Product

# подключение к Redis
r = redis.Redis(host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB)


class Recommender(object):

    def get_product_key(self, id):
        return f'product:{id}:purchased_with'

    def products_bought(self, products):
        product_ids = [p.id for p in products]
        for product_id in product_ids:
            for with_id in product_ids:
                # получите другие товары, купленные вместе с каждым товаром
                if product_id != with_id:
                    # увеличить балл для продукта, приобретенного вместе
                    r.zincrby(self.get_product_key(product_id),
                              1,
                              with_id)

    def suggest_products_for(self, products, max_results=6):
        product_ids = [p.id for p in products]
        if len(products)  == 1:
            # только 1 товар
            suggestions = r.zrange(
                self.get_product_key(product_ids[0]),
                0, -1, desc=True)[:max_results]
        else:
            # сгенерировать временный ключ
            flat_ids = ''.join([str(id) for id in product_ids])
            tmp_key = f'tmp_{flat_ids}'
            # несколько продуктов, объедините оценки всех продуктов
            # сохраняем получившийся отсортированный набор во временном ключе
            keys = [self.get_product_key(id) for id in product_ids]
            r.zunionstore(tmp_key, keys)
            # удалить идентификаторы продуктов, для которых рекомендуется
            r.zrem(tmp_key, *product_ids)
            # получить идентификаторы продуктов по их оценке, сортировка descendant
            suggestions = r.zrange(tmp_key, 0, -1, desc=True)[:max_results]
            # удалить временный ключ
            r.delete(tmp_key)
        suggested_products_ids = [int(id) for id in suggestions]
        # получить рекомендуемые товары и отсортировать их по порядку появления
        suggested_products = list(Product.objects.filter(id__in=suggested_products_ids))
        suggested_products.sort(key=lambda x: suggested_products_ids.index(x.id))
        return suggested_products

    def clear_purchases(self):
        for id in Product.objects.values_list('id', flat=True):
            r.delete(self.get_product_key(id))
