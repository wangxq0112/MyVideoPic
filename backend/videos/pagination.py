"""
分页 —— 所有列表接口共用.

允许前端在上限内自定义每页条数：媒体网格用默认 50 条配合触底加载，
历史抽屉一次要 100 条以上，用 ?page_size= 覆盖即可。
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
