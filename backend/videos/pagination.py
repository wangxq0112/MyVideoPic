"""
分页 —— 所有列表接口共用.

允许前端在上限内自定义每页条数：媒体网格显式请求 24 条并使用页码导航，
播放器侧栏可请求 200 条，其他列表按各自场景用 ?page_size= 覆盖即可。
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200
